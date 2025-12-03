#!/usr/bin/env python3
"""
LLMC RAG Service - Unified daemon for RAG indexing, enrichment, and embedding.

Replaces:
- indexenrich.sh
- qwen_enrich_batch.py
- rag_refresh.sh
- start_rag_refresh_loop.sh
- All the other script babies

Usage:
    llmc-rag-service start [--interval 180]
    llmc-rag-service stop
    llmc-rag-service status
    llmc-rag-service register <repo_path>
    llmc-rag-service unregister <repo_path>
    llmc-rag-service clear-failures [--repo <path>]
"""

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
from typing import Any

from tools.rag.config import get_vacuum_interval_hours, load_config

try:  # Python 3.11+
    import tomllib  # type: ignore
except Exception:
    tomllib = None  # type: ignore

try:
    # scripts is added to sys.path by scripts/llmc-rag-service wrapper
    from scripts.llmc_log_manager import LLMCLogManager  # type: ignore
except Exception:
    LLMCLogManager = None  # type: ignore

# State file locations (override via env for constrained environments)
_state_override = os.environ.get("LLMC_RAG_SERVICE_STATE")
if _state_override:
    STATE_FILE = Path(os.path.expanduser(_state_override)).resolve()
else:
    STATE_FILE = Path.home() / ".llmc" / "rag-service.json"

_failure_override = os.environ.get("LLMC_RAG_FAILURE_DB")
if _failure_override:
    FAILURE_DB = Path(os.path.expanduser(_failure_override)).resolve()
else:
    FAILURE_DB = Path.home() / ".llmc" / "rag-failures.db"

SERVICE_UNIT = "llmc-rag.service"

try:
    MAX_FAILURES = int(os.environ.get("LLMC_RAG_MAX_FAILURES", "3"))
except ValueError:
    MAX_FAILURES = 3  # 3 strikes and you're out


def print_help():
    """Print beautiful help screen."""
    print("""
LLMC RAG Service
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The intelligent RAG enrichment daemon for LLMC

Usage:
  llmc-rag <command> [options]

Service Management:
  start                Start the RAG service (systemd daemon)
  stop                 Stop the RAG service
  restart              Restart the RAG service
  status               Show service status and repo details
  logs [-f] [-n N]     View service logs (use -f to follow)
  enable               Enable service to start on user login
  disable              Disable service auto-start on user login

Repository Management:
  repo add <path>      Register a repository for enrichment
  repo remove <path>   Unregister a repository
  repo list            List all registered repositories

Health & Diagnostics:
  health               Check Ollama endpoint availability
  config               Show current service configuration
  failures             Show failure cache
  failures clear       Clear failure cache (optionally per repo)

Advanced:
  interval <seconds>   Change enrichment cycle interval
  force-cycle          Trigger immediate enrichment cycle
  exorcist <path>      Nuclear option: completely rebuild RAG database

Examples:
  llmc-rag repo add /home/you/src/llmc
  llmc-rag start
  llmc-rag logs -f
  llmc-rag health
  llmc-rag status
  llmc-rag enable
  llmc-rag disable

For detailed help: llmc-rag help <command>
""")


class ServiceState:
    """Manage service state persistence."""

    def __init__(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _load(self) -> dict:
        defaults: dict[str, Any] = {
            "repos": [],
            "pid": None,
            "status": "stopped",
            "last_cycle": None,
            "interval": 180,
            "last_vacuum": {},
        }
        if STATE_FILE.exists():
            try:
                loaded = json.loads(STATE_FILE.read_text())
                # merge loaded into defaults to ensure new keys exist
                defaults.update(loaded)
            except Exception:
                pass
        return defaults

    def _refresh_from_disk(self) -> None:
        """
        Refresh selected fields from the persisted state file.

        This is used by the long-running daemon before it writes any updates,
        so that repo add/remove operations performed by short-lived CLI
        processes are not accidentally clobbered by a stale in-memory copy.
        """
        if not STATE_FILE.exists():
            return
        try:
            data = json.loads(STATE_FILE.read_text())
        except Exception:
            # On any parse error, keep existing in-memory state.
            return
        if not isinstance(data, dict):
            return
        for key in ("repos", "interval"):
            if key in data:
                self.state[key] = data[key]

    def save(self):
        STATE_FILE.write_text(json.dumps(self.state, indent=2))

    def add_repo(self, repo_path: str):
        repo_path = str(Path(repo_path).resolve())
        if repo_path not in self.state["repos"]:
            self.state["repos"].append(repo_path)
            self.save()
            return True
        return False

    def remove_repo(self, repo_path: str):
        repo_path = str(Path(repo_path).resolve())
        if repo_path in self.state["repos"]:
            self.state["repos"].remove(repo_path)
            self.save()
            return True
        return False

    def set_running(self, pid: int):
        # Always refresh repos/interval from disk before updating runtime fields
        # so we do not overwrite CLI-driven changes from a long-lived daemon.
        self._refresh_from_disk()
        self.state["pid"] = pid
        self.state["status"] = "running"
        self.save()

    def set_stopped(self):
        # Same reasoning as set_running: avoid clobbering repo/interval changes
        # made by other processes that share the state file.
        self._refresh_from_disk()
        self.state["pid"] = None
        self.state["status"] = "stopped"
        self.save()

    def update_cycle(self):
        # Before recording the latest cycle timestamp, pull any updated repos
        # and interval from disk so daemon loops honor external CLI changes.
        self._refresh_from_disk()
        self.state["last_cycle"] = datetime.now(UTC).isoformat()
        self.save()

    def get_last_vacuum(self, repo_path: str) -> float:
        """Get timestamp of last vacuum for a repo (0.0 if never)."""
        vacuums = self.state.get("last_vacuum", {})
        # Ensure we handle case where last_vacuum might be missing in old state files
        if not isinstance(vacuums, dict):
            vacuums = {}
        return float(vacuums.get(repo_path, 0.0))

    def update_last_vacuum(self, repo_path: str):
        """Record vacuum timestamp for a repo."""
        self._refresh_from_disk()
        if "last_vacuum" not in self.state or not isinstance(self.state["last_vacuum"], dict):
            self.state["last_vacuum"] = {}
        self.state["last_vacuum"][repo_path] = time.time()
        self.save()

    def is_running(self) -> bool:
        if self.state["pid"] is None:
            return False
        # Check if PID exists
        try:
            os.kill(self.state["pid"], 0)
            return True
        except OSError:
            return False


class FailureTracker:
    """Track and manage enrichment failures."""

    def __init__(self):
        FAILURE_DB.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(FAILURE_DB))
        self._init_db()
        # Determine failure threshold: env > llmc.toml > default.
        env_raw = os.environ.get("LLMC_RAG_MAX_FAILURES")
        max_failures = MAX_FAILURES
        if env_raw:
            try:
                val = int(env_raw)
                if val > 0:
                    max_failures = val
            except ValueError:
                pass
        else:
            try:
                cfg = load_config()
                enrichment_cfg = cfg.get("enrichment") or {}
                cfg_val = enrichment_cfg.get("max_failures_per_span")
                if isinstance(cfg_val, int) and cfg_val > 0:
                    max_failures = int(cfg_val)
            except Exception:
                pass
        self.max_failures = max_failures

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS failures (
                span_hash TEXT,
                repo TEXT,
                failure_count INTEGER DEFAULT 1,
                last_attempted TEXT,
                reason TEXT,
                PRIMARY KEY (span_hash, repo)
            )
        """)
        self.conn.commit()

    def record_failure(self, span_hash: str, repo: str, reason: str):
        """Record a span-level failure, increment count."""
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            """
            INSERT INTO failures (span_hash, repo, failure_count, last_attempted, reason)
            VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(span_hash, repo) DO UPDATE SET
                failure_count = failure_count + 1,
                last_attempted = ?,
                reason = ?
        """,
            (span_hash, repo, now, reason, now, reason),
        )

    def record_repo_failure(self, repo: str, reason: str):
        """Record a repository-level failure."""
        # Use a special span_hash for repo-level failures
        span_hash = f"repo:{repo}"
        self.record_failure(span_hash, repo, reason)
        self.conn.commit()

    def is_failed(self, span_hash: str, repo: str) -> bool:
        """Check if span has hit failure threshold."""
        cursor = self.conn.execute(
            "SELECT failure_count FROM failures WHERE span_hash = ? AND repo = ?", (span_hash, repo)
        )
        row = cursor.fetchone()
        limit = getattr(self, "max_failures", MAX_FAILURES)
        if row and row[0] >= limit:
            return True
        return False

    def get_failures(self, repo: str | None = None) -> list:
        """Get all failures, optionally filtered by repo."""
        if repo:
            cursor = self.conn.execute(
                "SELECT span_hash, repo, failure_count, last_attempted, reason FROM failures WHERE repo = ?",
                (repo,),
            )
        else:
            cursor = self.conn.execute(
                "SELECT span_hash, repo, failure_count, last_attempted, reason FROM failures"
            )
        return cursor.fetchall()

    def clear_failures(self, repo: str | None = None):
        """Clear all failures, optionally for specific repo."""
        if repo:
            self.conn.execute("DELETE FROM failures WHERE repo = ?", (repo,))
        else:
            self.conn.execute("DELETE FROM failures")
        self.conn.commit()

    def get_stats(self, repo: str) -> dict:
        """Get failure stats for a repo."""
        cursor = self.conn.execute(
            "SELECT COUNT(*), SUM(failure_count) FROM failures WHERE repo = ?", (repo,)
        )
        row = cursor.fetchone()
        return {"failed_spans": row[0] or 0, "total_failures": row[1] or 0}


def _stream_systemd_logs_follow(lines: int) -> int:
    """Poll systemd journal to approximate `tail -f` without inotify watches."""
    cursor: str | None = None
    # Initial command: tail-style view with cursor
    cmd: list[str] = [
        "journalctl",
        "--user",
        "-u",
        SERVICE_UNIT,
        "-n",
        str(lines),
        "--show-cursor",
        "--no-pager",
    ]
    try:
        while True:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                err = (result.stderr or "").strip() or f"journalctl exited with {result.returncode}"
                print(f"[logs] journalctl error: {err}", file=sys.stderr)
                return 1

            output = result.stdout or ""
            new_cursor: str | None = None
            if output:
                out_lines = []
                for line in output.splitlines():
                    if line.startswith("-- cursor: "):
                        new_cursor = line.split(":", 1)[1].strip()
                    elif line.startswith("-- No entries --"):
                        # No new logs in this window; stay quiet and keep polling.
                        continue
                    else:
                        out_lines.append(line)
                if out_lines:
                    print("\n".join(out_lines))

            if new_cursor:
                cursor = new_cursor

            if cursor is None:
                cmd = [
                    "journalctl",
                    "--user",
                    "-u",
                    SERVICE_UNIT,
                    "-n",
                    str(lines),
                    "--show-cursor",
                    "--no-pager",
                ]
            else:
                cmd = [
                    "journalctl",
                    "--user",
                    "-u",
                    SERVICE_UNIT,
                    "--after-cursor",
                    cursor,
                    "--show-cursor",
                    "--no-pager",
                ]

            time.sleep(2.0)
    except KeyboardInterrupt:
        print()
        return 0


class RAGService:
    """Main RAG service orchestrator."""

    def __init__(self, state: ServiceState, tracker: FailureTracker):
        self.state = state
        self.tracker = tracker
        self.running = True
        # Load logging configuration for optional auto-rotation
        self._repo_root = Path(__file__).resolve().parents[2]
        self._logging_cfg = self._load_logging_cfg(self._repo_root)
        self._toml_cfg = self._load_full_toml(self._repo_root)
        self._daemon_cfg = self._toml_cfg.get("daemon", {})
        self._last_rotate: float = 0.0
        self._log_manager = None
        if LLMCLogManager is not None:
            max_mb = int(self._logging_cfg.get("max_file_size_mb", 10))
            keep_lines = int(self._logging_cfg.get("keep_jsonl_lines", 1000))
            enabled = bool(self._logging_cfg.get("enable_rotation", True))
            try:
                self._log_manager = LLMCLogManager(max_mb, keep_lines, enabled)
            except Exception:
                self._log_manager = None

    def handle_signal(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        self.running = False

    def _load_logging_cfg(self, repo_root: Path) -> dict:
        """Load [logging] section from llmc.toml at repo root if available."""
        if tomllib is None:
            return {}
        cfg_path = repo_root / "llmc.toml"
        if not cfg_path.exists():
            # Fallback to repo root relative to this file
            # tools/rag/service.py -> ../../llmc.toml
            dev_cfg = Path(__file__).resolve().parents[2] / "llmc.toml"
            if dev_cfg.exists():
                cfg_path = dev_cfg
            else:
                return {}
        try:
            with cfg_path.open("rb") as fh:
                data = tomllib.load(fh) or {}
            section = data.get("logging") or {}
            return section if isinstance(section, dict) else {}
        except Exception:
            return {}

    def _load_full_toml(self, repo_root: Path) -> dict:
        """Load entire llmc.toml to support other sections (optional)."""
        if tomllib is None:
            return {}
        cfg_path = repo_root / "llmc.toml"
        if not cfg_path.exists():
            return {}
        try:
            with cfg_path.open("rb") as fh:
                data = tomllib.load(fh) or {}
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def run_rag_cli(self, repo: Path, command: list) -> tuple[bool, str]:
        """Run a RAG CLI command for a repo. DEPRECATED - use runner module instead."""
        try:
            result = subprocess.run(
                ["python3", "-m", "tools.rag.cli"] + command,  # Fixed: python -> python3
                check=False,
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout per operation
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Operation timed out"
        except Exception as e:
            return False, str(e)

    def process_repo(self, repo_path: str) -> bool:
        """Process one repo: sync, enrich, embed with REAL LLMs.
        
        Returns:
            bool: True if any work was done (changes synced, spans enriched, etc.), False otherwise.
        """
        repo = Path(repo_path)
        if not repo.exists():
            print(f"⚠️  Repo not found: {repo_path}")
            return False

        print(f"🔄 Processing {repo.name}...")
        work_done = False

        # Import proper runner functions
        import sys

        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))

        try:
            from tools.rag.config import index_path_for_write
            from tools.rag.runner import detect_changes, run_embed, run_sync
        except ImportError as e:
            print(f"  ⚠️  Failed to import RAG runner: {e}")
            return False

        # Step 1: Detect and sync changed files
        try:
            index_path = index_path_for_write(repo)
            changes = detect_changes(repo, index_path=index_path)
            if changes:
                run_sync(repo, changes)
                print(f"  ✅ Synced {len(changes)} changed files")
                work_done = True
            else:
                print("  ℹ️  No file changes detected")
        except Exception as e:
            print(f"  ⚠️  Sync failed: {e}")
            # Continue anyway - enrichment might still work

        # Step 2: Enrich pending spans using EnrichmentPipeline
        try:
            from tools.rag.enrichment_pipeline import EnrichmentPipeline, build_enrichment_prompt
            from tools.rag.enrichment_adapters.ollama import OllamaBackend
            from tools.rag.enrichment_router import build_router_from_toml
            from tools.rag.database import Database
            
            # Load configuration from target repo (preferred) or service defaults
            repo_cfg = self._load_full_toml(repo)
            enrichment_cfg = repo_cfg.get("enrichment") or self._toml_cfg.get("enrichment") or {}
            
            batch_size = int(enrichment_cfg.get("batch_size", 50))
            cooldown = int(os.getenv("ENRICH_COOLDOWN", "0"))
            
            runner_cfg = enrichment_cfg.get("runner", {})
            code_first = bool(runner_cfg.get("code_first_default", False))
            starvation_high = int(runner_cfg.get("starvation_ratio_high", 5))
            starvation_low = int(runner_cfg.get("starvation_ratio_low", 1))
            
            # Get database
            index_path = index_path_for_write(repo)
            db = Database(index_path)
            
            try:
                # Build router from repo config
                router = build_router_from_toml(repo)
                
                # Create pipeline
                pipeline = EnrichmentPipeline(
                    db=db,
                    router=router,
                    backend_factory=OllamaBackend.from_spec,
                    prompt_builder=build_enrichment_prompt,
                    repo_root=repo,
                    max_failures_per_span=self.tracker.max_failures,
                    cooldown_seconds=cooldown,
                    code_first=code_first,
                    starvation_ratio_high=starvation_high,
                    starvation_ratio_low=starvation_low,
                )
                
                print(f"  🤖 Enriching with EnrichmentPipeline (batch_size={batch_size})", flush=True)
                
                def progress_cb(current, total):
                    if current % 5 == 0 or current == total:
                        print(f"    ... processed {current}/{total} spans", flush=True)

                result = pipeline.process_batch(
                    limit=batch_size, 
                    stop_check=lambda: not self.running,
                    progress_callback=progress_cb
                )
                
                # Report results
                if result.attempted > 0:
                    work_done = True
                    print(f"  ✅ Enriched {result.succeeded}/{result.attempted} spans ({result.success_rate:.0%} success)")
                    if result.failed > 0:
                        print(f"     ⚠️  {result.failed} failures, {result.skipped} skipped")
                else:
                    print("  ℹ️  No spans pending enrichment")
            finally:
                db.close()
        except Exception as e:
            print(f"  ⚠️  Enrichment failed: {e}")
            import traceback
            traceback.print_exc()

        # RAG doctor: quick index/enrichment health snapshot
        try:
            from tools.rag.doctor import format_rag_doctor_summary, run_rag_doctor

            doctor_result = run_rag_doctor(repo)
            print(format_rag_doctor_summary(doctor_result, repo.name))
        except Exception as e:
            print(f"  ⚠️  RAG doctor failed: {e}")

        # Step 3: Generate embeddings for enriched spans
        try:
            embed_limit = int(os.getenv("ENRICH_EMBED_LIMIT", "100"))
            embed_result = run_embed(repo, limit=embed_limit)
            # Check if embedding actually did work
            if embed_result and isinstance(embed_result, dict):
                embedded = embed_result.get("embedded", 0)
                if embedded > 0:
                    work_done = True
                    print(f"  ✅ Generated {embedded} embeddings")
                else:
                    print("  ℹ️  No spans pending embedding")
            else:
                print(f"  ✅ Embedding complete (limit={embed_limit})")
        except Exception as e:
            print(f"  ⚠️  Embedding failed: {e}")

        # Step 4: Quality check (if enabled)
        if os.getenv("ENRICH_QUALITY_CHECK", "on").lower() == "on":
            try:
                from tools.rag.quality import format_quality_summary, run_quality_check

                quality_result = run_quality_check(repo)
                print(format_quality_summary(quality_result, repo.name))

                # Log quality issues
                if quality_result["status"] == "FAIL":
                    self.tracker.record_repo_failure(
                        str(repo),
                        f"Quality check failed: score {quality_result['quality_score']:.1f}%, "
                        f"{quality_result.get('placeholder_count', 0)} placeholder, "
                        f"{quality_result.get('empty_count', 0)} empty, "
                        f"{quality_result.get('short_count', 0)} short",
                    )
            except Exception as e:
                print(f"  ⚠️  Quality check failed: {e}")

        # Step 5: Rebuild RAG Graph (Unified CLI support)
        try:
            from tools.rag_nav.tool_handlers import build_graph_for_repo

            print("  📊 Rebuilding RAG Graph...")
            status = build_graph_for_repo(repo)
            print("  ✅ Graph rebuilt successfully")
        except Exception as e:
            print(f"  ⚠️  Graph build failed: {e}")

        # Step 6: Database Maintenance (Vacuum)
        try:
            vacuum_interval_hours = get_vacuum_interval_hours(repo)
            last_vacuum = self.state.get_last_vacuum(str(repo))
            now = time.time()
            if now - last_vacuum > vacuum_interval_hours * 3600:
                print("  🧹 Running database vacuum...")
                from tools.rag.config import index_path_for_write
                from tools.rag.database import Database

                db_path = index_path_for_write(repo)
                db = Database(db_path)
                db.vacuum()
                db.close()

                self.state.update_last_vacuum(str(repo))
                print("  ✅ Database vacuum complete")
                work_done = True
        except Exception as e:
            print(f"  ⚠️  Database vacuum failed: {e}")

        if not work_done:
            print(f"  ℹ️  {repo.name}: Nothing to do")
        else:
            print(f"  ✅ {repo.name} processing complete")
        
        return work_done

    def get_repo_stats(self, repo_path: str) -> dict:
        """Get stats for a repo."""
        repo = Path(repo_path)
        success, output = self.run_rag_cli(repo, ["stats", "--json"])
        if success:
            try:
                stats = json.loads(output)
                failure_stats = self.tracker.get_stats(repo_path)
                stats.update(failure_stats)
                return dict(stats)
            except json.JSONDecodeError:
                pass
        return {}

    def run_loop(self, interval: int):
        """Main service loop with idle throttling."""
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)

        # Set process nice level to lower priority
        nice_level = self._daemon_cfg.get("nice_level", 10)
        try:
            current = os.nice(0)
            os.nice(nice_level - current)  # Adjust relative to current
            print(f"   Nice level: +{nice_level}")
        except (OSError, PermissionError) as e:
            print(f"   ⚠️  Could not set nice level: {e}")

        self.state.set_running(os.getpid())
        print(f"🚀 RAG service started (PID {os.getpid()})")
        print(f"   Tracking {len(self.state.state['repos'])} repos")
        print(f"   Interval: {interval}s")
        print(f"   Idle backoff: enabled (max {self._daemon_cfg.get('idle_backoff_max', 10)}x)")
        print()

        # Idle tracking
        idle_cycles = 0
        max_mult = self._daemon_cfg.get("idle_backoff_max", 10)
        base = self._daemon_cfg.get("idle_backoff_base", 2)

        while self.running:
            cycle_start = time.time()
            work_done = False

            for repo in self.state.state["repos"]:
                if not self.running:
                    break
                if self.process_repo(repo):
                    work_done = True

            self.state.update_cycle()
            
            # Backoff logic
            if work_done:
                idle_cycles = 0  # Reset on any work
            else:
                idle_cycles += 1
            
            # Optional: auto-rotate service logs based on config
            try:
                if self._log_manager is not None:
                    rotation_interval = int(self._logging_cfg.get("auto_rotation_interval", 0))
                    log_dir_val = self._logging_cfg.get("log_directory", "logs")
                    log_dir = Path(str(log_dir_val))
                    if not log_dir.is_absolute():
                        log_dir = (self._repo_root / log_dir).resolve()
                    now = time.time()
                    if rotation_interval == 0 or now - self._last_rotate >= rotation_interval:
                        result = self._log_manager.rotate_logs(log_dir)
                        self._last_rotate = now
                        if result.get("rotated_files", 0) > 0:
                            print(f"🔄 Rotated {result['rotated_files']} log files")
            except Exception as e:
                print(f"  ⚠️  Log rotation check failed: {e}")

            # Calculate sleep with exponential backoff when idle
            multiplier = min(base ** idle_cycles, max_mult)
            target_sleep = interval * multiplier
            elapsed = time.time() - cycle_start
            sleep_time = max(0, target_sleep - elapsed)

            if sleep_time > 0 and self.running:
                if idle_cycles > 0:
                    print(f"💤 Idle x{idle_cycles} → sleeping {int(sleep_time)}s...\n")
                else:
                    print(f"💤 Sleeping {int(sleep_time)}s...\n")
                self._interruptible_sleep(sleep_time)

        self.state.set_stopped()
        print("👋 RAG service stopped")
    def _interruptible_sleep(self, seconds: float):
        """Sleep in 5s chunks so signals are handled promptly."""
        chunk = 5.0
        remaining = seconds
        while remaining > 0 and self.running:
            time.sleep(min(chunk, remaining))
            remaining -= chunk



def cmd_start(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Start the service via systemd."""
    from .service_daemon import SystemdManager

    repo_root = Path(__file__).resolve().parents[2]
    systemd = SystemdManager(repo_root)

    if not state.state["repos"]:
        print("❌ No repos registered. Use 'llmc-rag repo add' first.")
        return 1

    # Check if systemd is available
    if not systemd.is_systemd_available():
        print("⚠️  Systemd not available - using fallback fork() mode")
        return cmd_start_fork(args, state, tracker)

    # Check if already running
    status = systemd.status()
    if status["running"]:
        print(f"✅ Service already running (PID {status['pid']})")
        return 0

    # Update state with interval
    state.state["interval"] = args.interval
    state.save()

    # Start via systemd
    success, message = systemd.start()
    if not success:
        print(f"❌ Failed to start: {message}")
        return 1

    # Verify service actually started (give it 2 seconds)
    import time

    time.sleep(2)
    status = systemd.status()

    if not status["running"]:
        print("❌ Service failed to start")
        if "status_text" in status:
            # Show relevant error from systemctl status
            for line in status["status_text"].split("\n"):
                if "failed" in line.lower() or "error" in line.lower():
                    print(f"   {line.strip()}")
        print("\n📋 Check logs: llmc-rag logs")
        return 1

    print(f"🚀 Service started (PID {status['pid']})")
    print(f"   Tracking {len(state.state['repos'])} repos")
    print(f"   Interval: {args.interval}s")
    print("\n📋 View logs: llmc-rag logs -f")
    return 0


def cmd_start_fork(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Fallback: Start the service via fork() when systemd unavailable."""
    if state.is_running():
        print(f"✅ Service already running (PID {state.state['pid']})")
        return 0

    # Fork to background
    pid = os.fork()
    if pid > 0:
        # Parent process
        print(f"🚀 Started RAG service in background (PID {pid})")
        print(f"   Tracking {len(state.state['repos'])} repos")
        print(f"   Interval: {args.interval}s")
        return 0

    # Child process continues
    os.setsid()
    sys.stdin.close()

    # Write daemon logs to a stable location
    log_dir = Path(os.path.expanduser("~/.llmc/logs/rag-daemon")).resolve()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "rag-service.log"
        log_file = open(log_path, "a", buffering=1, encoding="utf-8")
        sys.stdout = log_file
        sys.stderr = log_file
    except OSError:
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")

    service = RAGService(state, tracker)
    service.run_loop(args.interval)
    return 0


def cmd_stop(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Stop the service via systemd."""
    from .service_daemon import SystemdManager

    repo_root = Path(__file__).resolve().parents[2]
    systemd = SystemdManager(repo_root)

    if not systemd.is_systemd_available():
        # Fall back to PID-based stop
        return cmd_stop_fork(args, state, tracker)

    status = systemd.status()
    if not status["running"]:
        print("Service is not running")
        return 1

    success, message = systemd.stop()
    if success:
        print(f"✅ {message}")
        return 0
    else:
        print(f"❌ Failed to stop: {message}")
        return 1


def cmd_stop_fork(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Fallback: Stop the service via PID when systemd unavailable."""
    if not state.is_running():
        print("Service is not running")
        return 1

    pid = state.state["pid"]
    print(f"Stopping service (PID {pid})...")

    try:
        os.kill(pid, signal.SIGTERM)
        # Wait for graceful shutdown
        for _ in range(10):
            time.sleep(0.5)
            if not state.is_running():
                print("✅ Service stopped")
                return 0
        # Force kill if still running
        os.kill(pid, signal.SIGKILL)
        state.set_stopped()
        print("✅ Service force-stopped")
        return 0
    except ProcessLookupError:
        state.set_stopped()
        print("Service was not running (cleaned up stale PID)")
        return 0


def cmd_status(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Show service status."""
    print("LLMC RAG Service Status")
    print("=" * 50)

    if state.is_running():
        print(f"Status: 🟢 running (PID {state.state['pid']})")
    else:
        print("Status: 🔴 stopped")

    print(f"Repos tracked: {len(state.state['repos'])}")

    if state.state["repos"]:
        service = RAGService(state, tracker)
        for repo in state.state["repos"]:
            stats = service.get_repo_stats(repo)
            repo_name = Path(repo).name
            print(f"\n  📁 {repo_name}")
            print(f"     Path: {repo}")
            if stats:
                print(f"     Spans: {stats.get('spans', 0)}")
                print(f"     Enriched: {stats.get('enrichments', 0)}")
                print(f"     Embedded: {stats.get('embeddings', 0)}")
                failed = stats.get("failed_spans", 0)
                if failed > 0:
                    print(f"     Failed: {failed} (permanent)")

    if state.state["last_cycle"]:
        last = datetime.fromisoformat(state.state["last_cycle"])
        ago = (datetime.now(UTC) - last).total_seconds()
        print(f"\nLast cycle: {int(ago)}s ago")

    return 0


def cmd_register(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Register a repo - register + /full/path"""
    repo_path = Path(args.repo_path).resolve()
    # Basic path validation
    errors: list[str] = []
    warnings: list[str] = []
    if not repo_path.exists() or not repo_path.is_dir():
        print(f"Error: Path not found or not a directory: {repo_path}")
        return 1
    # Permission checks: require read, write, and execute on directory
    if not os.access(repo_path, os.R_OK):
        errors.append("Directory is not readable")
    if not os.access(repo_path, os.W_OK):
        errors.append("Directory is not writable (cannot create .rag/logs)")
    if not os.access(repo_path, os.X_OK):
        errors.append("Directory is not accessible (execute permission missing)")
    # Git check: warn if not a git repo (we can still operate via os.walk fallback)
    try:
        rc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=False,
            cwd=repo_path,
            capture_output=True,
        )
        if rc.returncode != 0:
            warnings.append("Not a git repository; falling back to filesystem scan")
    except Exception:
        warnings.append("Git not available; falling back to filesystem scan")
    if errors:
        print(f"Cannot register: {repo_path}")
        for e in errors:
            print(f"  ✖ {e}")
        return 1
    if warnings:
        print(f"Registering with warnings for: {repo_path}")
        for w in warnings:
            print(f"  ⚠ {w}")

    if state.add_repo(str(repo_path)):
        print(f"Registered: {repo_path}")
        return 0
    else:
        print(f"Already registered: {repo_path}")
        return 1


def cmd_unregister(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Unregister a repo - unregister + /full/path"""
    repo_path = Path(args.repo_path).resolve()

    if state.remove_repo(str(repo_path)):
        print(f"Unregistered: {repo_path}")
        return 0
    else:
        print(f"Not registered: {repo_path}")
        return 1


def cmd_failures(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Manage failure cache - show or clear."""
    subcommand = getattr(args, "failures_command", None)

    if subcommand == "clear":
        # Clear failures
        repo = getattr(args, "repo", None)
        if repo:
            repo = str(Path(repo).resolve())
            tracker.clear_failures(repo)
            print(f"✅ Cleared failures for: {repo}")
        else:
            tracker.clear_failures()
            print("✅ Cleared all failures")
        return 0

    else:
        # Show failures (default)
        repo = getattr(args, "repo", None)
        failures = tracker.get_failures(repo)

        if not failures:
            print("✅ No failures recorded")
            return 0

        print("Failure Cache")
        print("=" * 50)

        by_repo: dict[str, list[tuple[str, int, object, str]]] = {}
        for span_hash, repo_path, fail_count, last_attempted, reason in failures:
            if repo_path not in by_repo:
                by_repo[repo_path] = []
            by_repo[repo_path].append((span_hash, fail_count, last_attempted, reason))

        for repo_path, repo_failures in by_repo.items():
            repo_name = Path(repo_path).name
            print(f"\n📁 {repo_name} ({len(repo_failures)} failures)")
            for span_hash, fail_count, last_attempted, reason in repo_failures[:5]:  # Show first 5
                # Extract filename from span_hash if it's a repo-level failure
                if span_hash.startswith("repo:"):
                    print(f"   ⚠️  Repository-level failure (x{fail_count})")
                else:
                    print(f"   ⚠️  Span {span_hash[:16]}... (x{fail_count})")
                print(f"      Reason: {reason}")

            if len(repo_failures) > 5:
                print(f"   ... and {len(repo_failures) - 5} more")

        print(f"\nTotal: {len(failures)} failed spans")
        print("\nTo clear: llmc-rag failures clear [--repo <path>]")
        return 0


def cmd_clear_failures(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Clear failure cache - backwards compat wrapper."""
    return cmd_failures(args, state, tracker)


def cmd_restart(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Restart the service via systemd."""
    from .service_daemon import SystemdManager

    repo_root = Path(__file__).resolve().parents[2]
    systemd = SystemdManager(repo_root)

    if not systemd.is_systemd_available():
        print("❌ Systemd not available - restart via stop+start")
        cmd_stop(args, state, tracker)
        time.sleep(2)
        return cmd_start(args, state, tracker)

    success, message = systemd.restart()
    if success:
        print(f"🔄 {message}")
        return 0
    else:
        print(f"❌ Failed to restart: {message}")
        return 1


def cmd_logs(args, state: ServiceState, tracker: FailureTracker) -> int:
    """View service logs."""
    from .service_daemon import SystemdManager

    repo_root = Path(__file__).resolve().parents[2]
    systemd = SystemdManager(repo_root)

    log_file = Path.home() / ".llmc" / "logs" / "rag-daemon" / "rag-service.log"

    # Prefer systemd journal when available and the service is active.
    if systemd.is_systemd_available():
        status = systemd.status()
        if status.get("active") or status.get("running"):
            print("LLMC RAG Service Logs (systemd journal)")
            print("========================================")
            print("Showing recent entries from systemd. For full history, use:")
            print("  journalctl --user -u llmc-rag.service\n")
            if args.follow:
                return _stream_systemd_logs_follow(args.lines)
            systemd.get_logs(lines=args.lines, follow=False)
            return 0

    # Fallback: file-based logs (fork mode or non-systemd environments).
    if log_file.exists():
        stat = log_file.stat()
        age_seconds = time.time() - stat.st_mtime
        age_hours = age_seconds / 3600.0
        print("LLMC RAG Service Logs (file)")
        print("================================")
        print(f"File: {log_file}")
        print(f"Last modified: {time.ctime(stat.st_mtime)} (~{age_hours:.1f}h ago)")
        print(
            f"Showing last {args.lines} lines; output may include historical entries "
            "from previous runs.\n"
        )
        if args.follow:
            subprocess.run(["tail", "-f", "-n", str(args.lines), str(log_file)], check=False)
        else:
            subprocess.run(["tail", "-n", str(args.lines), str(log_file)], check=False)
        return 0

    # If systemd is available but service is not active, allow journal access anyway.
    if systemd.is_systemd_available():
        print("LLMC RAG Service Logs (systemd journal - inactive service)")
        print("===========================================================")
        if args.follow:
            return _stream_systemd_logs_follow(args.lines)
        systemd.get_logs(lines=args.lines, follow=False)
        return 0

    # No logs available via file or systemd.
    print("❌ No logs available")
    print(f"   File logs: {log_file} (not found)")
    print("   Systemd: not available or no journal entries yet")
    return 1


def cmd_health(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Check Ollama endpoint health."""
    from .service_health import HealthChecker, parse_ollama_hosts_from_env

    endpoints = parse_ollama_hosts_from_env()

    if not endpoints:
        print("❌ No Ollama endpoints configured")
        print("\nSet ENRICH_OLLAMA_HOSTS environment variable:")
        print("  export ENRICH_OLLAMA_HOSTS='athena=http://192.168.5.20:11434'")
        return 1

    checker = HealthChecker(timeout=5.0)
    results = checker.check_all(endpoints)

    print(checker.format_results(results))

    # Return error if any endpoints are down
    unreachable = [r for r in results if not r.reachable]
    return 1 if unreachable else 0


def cmd_config(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Show current service configuration."""
    print("LLMC RAG Service Configuration")
    print("=" * 50)
    print()

    # State file
    print(f"State File: {STATE_FILE}")
    print(f"Failure DB: {FAILURE_DB}")
    print()

    # Service state
    print("Service State:")
    print(f"  Status: {state.state['status']}")
    print(f"  Interval: {state.state['interval']}s")
    print(f"  Registered Repos: {len(state.state['repos'])}")
    if state.state["last_cycle"]:
        print(f"  Last Cycle: {state.state['last_cycle']}")
    print()

    # Environment
    print("Environment:")
    env_vars = [
        "ENRICH_BACKEND",
        "ENRICH_ROUTER",
        "ENRICH_START_TIER",
        "ENRICH_BATCH_SIZE",
        "ENRICH_MAX_SPANS",
        "ENRICH_COOLDOWN",
        "ENRICH_OLLAMA_HOSTS",
        "ENRICH_QUALITY_CHECK",
    ]
    for var in env_vars:
        value = os.getenv(var, "(not set)")
        print(f"  {var}: {value}")

    return 0


def cmd_exorcist(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Nuclear option: rebuild RAG database."""
    from .service_exorcist import Exorcist

    repo = Path(args.path).resolve()

    if not repo.exists():
        print(f"❌ Repo not found: {repo}")
        return 1

    # Check if service is running and processing this repo
    if state.is_running() and str(repo) in state.state["repos"]:
        print("❌ Service is currently running and tracking this repo")
        print("\nStop the service first:")
        print("  llmc-rag stop")
        print("\nOr remove this repo temporarily:")
        print(f"  llmc-rag repo remove {repo}")
        return 1

    exorcist = Exorcist(repo)
    return exorcist.execute(dry_run=args.dry_run)


def cmd_interval(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Change enrichment cycle interval."""
    new_interval = args.seconds

    if new_interval < 60:
        print("❌ Interval must be at least 60 seconds")
        return 1

    state.state["interval"] = new_interval
    state.save()

    print(f"✅ Interval set to {new_interval}s")

    if state.is_running():
        print("\n⚠️  Service is running. Restart for changes to take effect:")
        print("  llmc-rag restart")

    return 0


def cmd_force_cycle(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Trigger immediate enrichment cycle."""
    if not state.is_running():
        print("❌ Service is not running")
        print("\nStart the service first:")
        print("  llmc-rag start")
        return 1

    print("⚠️  Force cycle not yet implemented")
    print("    (Would send signal to running service to trigger immediate cycle)")
    return 1


def cmd_repo(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Handle repo subcommands."""
    if args.repo_command == "add":
        return cmd_register(args, state, tracker)
    elif args.repo_command == "remove":
        return cmd_unregister(args, state, tracker)
    elif args.repo_command == "list":
        print("Registered Repositories:")
        if not state.state["repos"]:
            print("  (none)")
            return 0
        for repo in state.state["repos"]:
            print(f"  📁 {repo}")
        return 0
    return 1


def cmd_enable(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Enable service to start on boot."""
    from .service_daemon import SystemdManager

    repo_root = Path(__file__).resolve().parents[2]
    systemd = SystemdManager(repo_root)

    if not systemd.is_systemd_available():
        print("❌ Systemd not available on this system")
        return 1

    success, message = systemd.enable()
    if success:
        print(f"✅ {message}")
        return 0
    else:
        print(f"❌ Failed to enable: {message}")
        return 1


def cmd_disable(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Disable service from starting on boot."""
    from .service_daemon import SystemdManager

    repo_root = Path(__file__).resolve().parents[2]
    systemd = SystemdManager(repo_root)

    if not systemd.is_systemd_available():
        print("❌ Systemd not available on this system")
        return 1

    success, message = systemd.disable()
    if success:
        print(f"✅ {message}")
        return 0
    else:
        print(f"❌ Failed to disable: {message}")
        return 1


def cmd_daemon_loop(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Internal command for systemd to run the daemon loop."""
    service = RAGService(state, tracker)
    service.run_loop(args.interval)
    return 0


def main(argv: list[str] | None | None = None):
    if argv is None:
        argv = sys.argv[1:]

    # Friendly top-level help for `llmc-rag` with no args or --help.
    if not argv or argv[0] in ("-h", "--help"):
        print_help()
        return 0

    parser = argparse.ArgumentParser(description="LLMC RAG Service", add_help=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Service management
    start_p = subparsers.add_parser("start", help="Start the service")
    start_p.add_argument("--interval", type=int, default=180, help="Loop interval in seconds")
    start_p.add_argument(
        "--daemon", action="store_true", help="Run in background (deprecated, uses systemd)"
    )

    stop_p = subparsers.add_parser("stop", help="Stop the service")
    restart_p = subparsers.add_parser("restart", help="Restart the service")
    status_p = subparsers.add_parser("status", help="Show service status")

    logs_p = subparsers.add_parser("logs", help="View service logs")
    logs_p.add_argument("-f", "--follow", action="store_true", help="Follow log output")
    logs_p.add_argument("-n", "--lines", type=int, default=50, help="Number of lines to show")

    # Repo management (NEW: subcommand style)
    repo_p = subparsers.add_parser("repo", help="Manage repositories")
    repo_sub = repo_p.add_subparsers(dest="repo_command", required=True)

    add_p = repo_sub.add_parser("add", help="Add a repository")
    add_p.add_argument("repo_path", help="Path to repository")

    remove_p = repo_sub.add_parser("remove", help="Remove a repository")
    remove_p.add_argument("repo_path", help="Path to repository")

    list_p = repo_sub.add_parser("list", help="List registered repositories")

    # Backwards compatibility - keep old commands
    reg_p = subparsers.add_parser("register", help="Register a repo (deprecated, use 'repo add')")
    reg_p.add_argument("repo_path", help="Path to repository")

    unreg_p = subparsers.add_parser(
        "unregister", help="Unregister a repo (deprecated, use 'repo remove')"
    )
    unreg_p.add_argument("repo_path", help="Path to repository")

    # Health & diagnostics
    health_p = subparsers.add_parser("health", help="Check Ollama endpoint health")
    config_p = subparsers.add_parser("config", help="Show current configuration")

    failures_p = subparsers.add_parser("failures", help="Manage failure cache")
    failures_sub = failures_p.add_subparsers(dest="failures_command")
    failures_show_p = failures_sub.add_parser("show", help="Show failures (default)")
    clear_fail_p = failures_sub.add_parser("clear", help="Clear failures")
    clear_fail_p.add_argument("--repo", help="Clear failures for specific repo only")

    # Backwards compat
    clear_p = subparsers.add_parser("clear-failures", help="Clear failure cache (deprecated)")
    clear_p.add_argument("--repo", help="Clear failures for specific repo only")

    # Advanced
    interval_p = subparsers.add_parser("interval", help="Change enrichment cycle interval")
    interval_p.add_argument("seconds", type=int, help="Interval in seconds")

    force_p = subparsers.add_parser("force-cycle", help="Trigger immediate enrichment cycle")

    exorcist_p = subparsers.add_parser("exorcist", help="Nuclear option: rebuild RAG database")
    exorcist_p.add_argument("path", help="Path to repository")
    exorcist_p.add_argument("--dry-run", action="store_true", help="Show what would be deleted")

    enable_p = subparsers.add_parser("enable", help="Enable service to start on boot")
    disable_p = subparsers.add_parser("disable", help="Disable service from starting on boot")

    # Hidden internal command for systemd
    daemon_p = subparsers.add_parser("_daemon_loop", help=argparse.SUPPRESS)
    daemon_p.add_argument("--interval", type=int, default=180)

    args = parser.parse_args(argv)

    try:
        state = ServiceState()
        tracker = FailureTracker()
    except PermissionError as exc:
        print(f"Error: cannot initialize RAG service state: {exc}")
        print(
            "Hint: set LLMC_RAG_SERVICE_STATE and LLMC_RAG_FAILURE_DB "
            "to writable paths (for example: .llmc/rag-service.json)."
        )
        return 1
    except Exception as exc:
        print(f"Error: failed to initialize RAG service: {exc}")
        return 1

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": cmd_status,
        "logs": cmd_logs,
        "repo": cmd_repo,
        "register": cmd_register,  # Backwards compat
        "unregister": cmd_unregister,  # Backwards compat
        "health": cmd_health,
        "config": cmd_config,
        "failures": cmd_failures,
        "clear-failures": cmd_clear_failures,  # Backwards compat
        "interval": cmd_interval,
        "force-cycle": cmd_force_cycle,
        "exorcist": cmd_exorcist,
        "enable": cmd_enable,
        "disable": cmd_disable,
        "_daemon_loop": cmd_daemon_loop,
    }

    return commands[args.command](args, state, tracker)


if __name__ == "__main__":
    sys.exit(main())

# INCREMENTAL TEST - will add 0-1 spans
