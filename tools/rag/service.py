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
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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

# Failure policy
MAX_FAILURES = 3  # 3 strikes and you're out


class ServiceState:
    """Manage service state persistence."""
    
    def __init__(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()
    
    def _load(self) -> dict:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
        return {
            "repos": [],
            "pid": None,
            "status": "stopped",
            "last_cycle": None,
            "interval": 180
        }
    
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
        self.state["pid"] = pid
        self.state["status"] = "running"
        self.save()
    
    def set_stopped(self):
        self.state["pid"] = None
        self.state["status"] = "stopped"
        self.save()
    
    def update_cycle(self):
        self.state["last_cycle"] = datetime.now(timezone.utc).isoformat()
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
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            INSERT INTO failures (span_hash, repo, failure_count, last_attempted, reason)
            VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(span_hash, repo) DO UPDATE SET
                failure_count = failure_count + 1,
                last_attempted = ?,
                reason = ?
        """, (span_hash, repo, now, reason, now, reason))

    def record_repo_failure(self, repo: str, reason: str):
        """Record a repository-level failure."""
        # Use a special span_hash for repo-level failures
        span_hash = f"repo:{repo}"
        self.record_failure(span_hash, repo, reason)
        self.conn.commit()
    
    def is_failed(self, span_hash: str, repo: str) -> bool:
        """Check if span has hit failure threshold."""
        cursor = self.conn.execute(
            "SELECT failure_count FROM failures WHERE span_hash = ? AND repo = ?",
            (span_hash, repo)
        )
        row = cursor.fetchone()
        if row and row[0] >= MAX_FAILURES:
            return True
        return False
    
    def get_failures(self, repo: Optional[str] = None) -> list:
        """Get all failures, optionally filtered by repo."""
        if repo:
            cursor = self.conn.execute(
                "SELECT span_hash, repo, failure_count, last_attempted, reason FROM failures WHERE repo = ?",
                (repo,)
            )
        else:
            cursor = self.conn.execute(
                "SELECT span_hash, repo, failure_count, last_attempted, reason FROM failures"
            )
        return cursor.fetchall()
    
    def clear_failures(self, repo: Optional[str] = None):
        """Clear all failures, optionally for specific repo."""
        if repo:
            self.conn.execute("DELETE FROM failures WHERE repo = ?", (repo,))
        else:
            self.conn.execute("DELETE FROM failures")
        self.conn.commit()
    
    def get_stats(self, repo: str) -> dict:
        """Get failure stats for a repo."""
        cursor = self.conn.execute(
            "SELECT COUNT(*), SUM(failure_count) FROM failures WHERE repo = ?",
            (repo,)
        )
        row = cursor.fetchone()
        return {
            "failed_spans": row[0] or 0,
            "total_failures": row[1] or 0
        }


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
            dev_cfg = (Path(__file__).resolve().parents[2] / "llmc.toml")
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
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=300  # 5 min timeout per operation
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Operation timed out"
        except Exception as e:
            return False, str(e)
    
    def process_repo(self, repo_path: str):
        """Process one repo: sync, enrich, embed with REAL LLMs."""
        repo = Path(repo_path)
        if not repo.exists():
            print(f"⚠️  Repo not found: {repo_path}")
            return
        
        print(f"🔄 Processing {repo.name}...")
        
        # Import proper runner functions
        import sys
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))
        
        try:
            from tools.rag.runner import run_enrich, run_sync, run_embed, detect_changes
            from tools.rag.config import index_path_for_write
        except ImportError as e:
            print(f"  ⚠️  Failed to import RAG runner: {e}")
            return
        
        # Step 1: Detect and sync changed files
        try:
            index_path = index_path_for_write(repo)
            changes = detect_changes(repo, index_path=index_path)
            if changes:
                run_sync(repo, changes)
                print(f"  ✅ Synced {len(changes)} changed files")
            else:
                print(f"  ℹ️  No file changes detected")
        except Exception as e:
            print(f"  ⚠️  Sync failed: {e}")
            # Continue anyway - enrichment might still work
        
        # Step 2: Enrich pending spans with REAL LLMs
        try:
            backend = os.getenv("ENRICH_BACKEND", "ollama")
            router = os.getenv("ENRICH_ROUTER", "on")
            start_tier = os.getenv("ENRICH_START_TIER", "7b")
            # Precedence: env > TOML > default
            if os.getenv("ENRICH_BATCH_SIZE") is not None:
                batch_size = int(os.getenv("ENRICH_BATCH_SIZE", "5"))
            else:
                batch_size = int((self._toml_cfg.get("enrichment", {}) or {}).get("batch_size", 5))
            max_spans = int(os.getenv("ENRICH_MAX_SPANS", "50"))
            cooldown = int(os.getenv("ENRICH_COOLDOWN", "0"))
            
            print(f"  🤖 Enriching with: backend={backend}, router={router}, tier={start_tier}")
            run_enrich(
                repo,
                backend=backend,
                router=router,
                start_tier=start_tier,
                batch_size=batch_size,
                max_spans=max_spans,
                cooldown=cooldown
            )
            print(f"  ✅ Enriched pending spans with real LLM summaries")
        except Exception as e:
            print(f"  ⚠️  Enrichment failed: {e}")
        
        # Step 3: Generate embeddings for enriched spans
        try:
            embed_limit = int(os.getenv("ENRICH_EMBED_LIMIT", "100"))
            run_embed(repo, limit=embed_limit)
            print(f"  ✅ Generated embeddings (limit={embed_limit})")
        except Exception as e:
            print(f"  ⚠️  Embedding failed: {e}")
        
        # Step 4: Quality check (if enabled)
        if os.getenv("ENRICH_QUALITY_CHECK", "on").lower() == "on":
            try:
                from tools.rag.quality import run_quality_check, format_quality_summary
                result = run_quality_check(repo)
                print(format_quality_summary(result, repo.name))
                
                # Log quality issues
                if result['status'] == 'FAIL':
                    self.tracker.record_repo_failure(
                        str(repo),
                        f"Quality check failed: score {result['quality_score']:.1f}%, "
                        f"{result.get('placeholder_count', 0)} placeholder, "
                        f"{result.get('empty_count', 0)} empty, "
                        f"{result.get('short_count', 0)} short"
                    )
            except Exception as e:
                print(f"  ⚠️  Quality check failed: {e}")

        # Step 5: Rebuild RAG Graph (Unified CLI support)
        try:
            from tools.rag_nav.tool_handlers import build_graph_for_repo
            print(f"  📊 Rebuilding RAG Graph...")
            status = build_graph_for_repo(repo)
            print(f"  ✅ Graph rebuilt: {status}")
        except Exception as e:
            print(f"  ⚠️  Graph build failed: {e}")
        
        print(f"  ✅ {repo.name} processing complete")
    
    def get_repo_stats(self, repo_path: str) -> dict:
        """Get stats for a repo."""
        repo = Path(repo_path)
        success, output = self.run_rag_cli(repo, ["stats", "--json"])
        if success:
            try:
                stats = json.loads(output)
                failure_stats = self.tracker.get_stats(repo_path)
                stats.update(failure_stats)
                return stats
            except json.JSONDecodeError:
                pass
        return {}
    
    def run_loop(self, interval: int):
        """Main service loop."""
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)
        
        self.state.set_running(os.getpid())
        print(f"🚀 RAG service started (PID {os.getpid()})")
        print(f"   Tracking {len(self.state.state['repos'])} repos")
        print(f"   Interval: {interval}s")
        print()
        
        while self.running:
            cycle_start = time.time()
            
            for repo in self.state.state["repos"]:
                if not self.running:
                    break
                self.process_repo(repo)
            
            self.state.update_cycle()
            # Optional: auto-rotate service logs based on config
            try:
                if self._log_manager is not None:
                    interval = int(self._logging_cfg.get("auto_rotation_interval", 0))
                    log_dir_val = self._logging_cfg.get("log_directory", "logs")
                    log_dir = Path(str(log_dir_val))
                    if not log_dir.is_absolute():
                        log_dir = (self._repo_root / log_dir).resolve()
                    now = time.time()
                    if interval == 0 or now - self._last_rotate >= interval:
                        result = self._log_manager.rotate_logs(log_dir)
                        self._last_rotate = now
                        if result.get("rotated_files", 0) > 0:
                            print(f"🔄 Rotated {result['rotated_files']} log files")
            except Exception as e:
                print(f"  ⚠️  Log rotation check failed: {e}")
            
            # Sleep for remaining interval
            elapsed = time.time() - cycle_start
            sleep_time = max(0, interval - elapsed)
            
            if sleep_time > 0 and self.running:
                print(f"💤 Sleeping {int(sleep_time)}s until next cycle...\n")
                time.sleep(sleep_time)
        
        self.state.set_stopped()
        print("👋 RAG service stopped")


def cmd_start(args, state: ServiceState, tracker: FailureTracker):
    """Start the service."""
    if state.is_running():
        print(f"Service already running (PID {state.state['pid']})")
        return 1
    
    if not state.state["repos"]:
        print("No repos registered. Use 'register' command first.")
        return 1
    
    # Fork to background if --daemon
    if args.daemon:
        pid = os.fork()
        if pid > 0:
            # Parent process
            print(f"Started RAG service in background (PID {pid})")
            return 0
        # Child process continues
        os.setsid()
        sys.stdin.close()
        # Write daemon logs to a stable location instead of /dev/null
        log_dir = Path(os.path.expanduser("~/.llmc/logs/rag-daemon")).resolve()
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "rag-service.log"
            log_file = open(log_path, "a", buffering=1, encoding="utf-8")
            sys.stdout = log_file
            sys.stderr = log_file
        except OSError:
            # Fall back to discarding output if logging cannot be configured
            sys.stdout = open(os.devnull, "w")
            sys.stderr = open(os.devnull, "w")
    
    service = RAGService(state, tracker)
    service.run_loop(args.interval)
    return 0


def cmd_stop(args, state: ServiceState, tracker: FailureTracker):
    """Stop the service."""
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
                print("Service stopped")
                return 0
        # Force kill if still running
        os.kill(pid, signal.SIGKILL)
        state.set_stopped()
        print("Service force-stopped")
        return 0
    except ProcessLookupError:
        state.set_stopped()
        print("Service was not running (cleaned up stale PID)")
        return 0


def cmd_status(args, state: ServiceState, tracker: FailureTracker):
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
                failed = stats.get('failed_spans', 0)
                if failed > 0:
                    print(f"     Failed: {failed} (permanent)")
    
    if state.state["last_cycle"]:
        last = datetime.fromisoformat(state.state["last_cycle"])
        ago = (datetime.now(timezone.utc) - last).total_seconds()
        print(f"\nLast cycle: {int(ago)}s ago")
    
    return 0


def cmd_register(args, state: ServiceState, tracker: FailureTracker):
    """Register a repo - register + /full/path """
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
        rc = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_path, capture_output=True)
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



def cmd_unregister(args, state: ServiceState, tracker: FailureTracker):
    """Unregister a repo - unregister + /full/path"""
    repo_path = Path(args.repo_path).resolve()
    
    if state.remove_repo(str(repo_path)):
        print(f"Unregistered: {repo_path}")
        return 0
    else:
        print(f"Not registered: {repo_path}")
        return 1


def cmd_clear_failures(args, state: ServiceState, tracker: FailureTracker):
    """Clear failure cache."""
    repo = args.repo
    if repo:
        repo = str(Path(repo).resolve())
        tracker.clear_failures(repo)
        print(f"Cleared failures for: {repo}")
    else:
        tracker.clear_failures()
        print("Cleared all failures")
    return 0


def main(argv: Optional[list[str]] | None = None):
    if argv is None:
        argv = sys.argv[1:]

    # Friendly top-level help for `llmc-rag-service` with no args or --help.
    if not argv or argv[0] in ("-h", "--help"):
        print(
            "LLMC RAG Service\n\n"
            "High-level manager for the LLMC RAG background service.\n\n"
            "Usage:\n"
            "  llmc-rag-service <command> [options]\n\n"
            "Commands:\n"
            "  register       Add a repo to the service\n"
            "  unregister     Remove a repo from the service\n"
            "  start          Start the background RAG service\n"
            "  stop           Stop the background RAG service\n"
            "  status         Show service + repo status\n"
            "  clear-failures Clear recorded failures (globally or per repo)\n\n"
            "Examples:\n"
            "  llmc-rag-service register /home/you/src/llmc\n"
            "  llmc-rag-service start --interval 300\n"
            "  llmc-rag-service status\n"
        )
        return 0

    parser = argparse.ArgumentParser(description="LLMC RAG Service")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # start command
    start_p = subparsers.add_parser("start", help="Start the service")
    start_p.add_argument("--interval", type=int, default=180, help="Loop interval in seconds")
    start_p.add_argument("--daemon", action="store_true", help="Run in background")
    
    # stop command
    subparsers.add_parser("stop", help="Stop the service")
    
    # status command
    subparsers.add_parser("status", help="Show service status")
    
    # register command
    reg_p = subparsers.add_parser("register", help="Register a repo")
    reg_p.add_argument("repo_path", help="Path to repository")
    
    # unregister command
    unreg_p = subparsers.add_parser("unregister", help="Unregister a repo")
    unreg_p.add_argument("repo_path", help="Path to repository")
    
    # clear-failures command
    clear_p = subparsers.add_parser("clear-failures", help="Clear failure cache")
    clear_p.add_argument("--repo", help="Clear failures for specific repo only")
    
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
        "status": cmd_status,
        "register": cmd_register,
        "unregister": cmd_unregister,
        "clear-failures": cmd_clear_failures,
    }
    
    return commands[args.command](args, state, tracker)


if __name__ == "__main__":
    sys.exit(main())

# INCREMENTAL TEST - will add 0-1 spans
