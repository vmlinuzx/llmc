# LLMC RAG Service CLI - Software Design Document (SDD)
**Author:** DC & Claude (Otto)  
**Date:** 2024-11-24  
**Status:** DRAFT - AWAITING DC APPROVAL  
**Branch:** CoupDeGras  
**Related:** RAG_SERVICE_CLI_HLD.md

---

## 1. Document Purpose

This SDD provides detailed technical specifications for implementing the LLMC RAG Service CLI as defined in RAG_SERVICE_CLI_HLD.md. This is the bridge between "what we're building" and "how we're building it."

---

## 2. File Structure & Organization

### 2.1 Current Structure
```
scripts/
  llmc-rag-service          # 17 lines, thin wrapper
  qwen_enrich_batch.py      # 2044 lines, SACRED LOGGING at line 1994

tools/rag/
  service.py                # 699 lines, orchestrator
  runner.py                 # 415 lines, pipeline executor
  [... other RAG modules]
```

### 2.2 New Structure
```
scripts/
  llmc-rag                  # NEW: Main CLI entry point (~200 lines)
  llmc-rag-service          # DEPRECATED: Keep as symlink for backwards compat
  qwen_enrich_batch.py      # UNCHANGED: Sacred logging preserved

tools/rag/
  service.py                # ENHANCED: Add systemd, exorcist, health (~900 lines)
  service_daemon.py         # NEW: Systemd integration (~150 lines)
  service_health.py         # NEW: Health checks (~100 lines)
  service_exorcist.py       # NEW: Database nuke (~200 lines)
  runner.py                 # UNCHANGED: Pipeline stays as-is
  [... other RAG modules]

~/.config/systemd/user/
  llmc-rag.service          # GENERATED: Systemd unit file
```

### 2.3 Why This Organization?

**scripts/llmc-rag** - Single entry point for all user interactions
- Handles argument parsing
- Routes to appropriate service module
- Provides beautiful help screen
- Zero logic, pure dispatch

**tools/rag/service_*.py** - Modular features
- Each feature in its own file
- Easy to test independently  
- Clean separation of concerns
- service.py coordinates, delegates to service_*.py

---

## 3. Module Designs

### 3.1 scripts/llmc-rag (Main CLI Entry Point)

**Purpose:** User-facing command dispatcher. Handles all CLI parsing and routing.

**Design:**
```python
#!/usr/bin/env python3
"""
LLMC RAG Service - Unified CLI
"""
import sys
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from tools.rag.service import main

if __name__ == "__main__":
    sys.exit(main())
```

**Why so simple?**
- Just a thin wrapper like current llmc-rag-service
- All logic stays in tools/rag/service.py
- Makes testing easier (test service.py directly)

---

### 3.2 tools/rag/service.py (Enhanced Orchestrator)

**Current:** 699 lines with start/stop/status/register/unregister  
**New:** ~900 lines adding systemd/health/logs/config/exorcist

**Key Changes:**

#### 3.2.1 New Command Structure
```python
def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point with enhanced help."""
    if not argv:
        argv = sys.argv[1:]
    
    # Show beautiful help for no args or --help
    if not argv or argv[0] in ("-h", "--help"):
        print_help()
        return 0
    
    parser = argparse.ArgumentParser(
        description="LLMC RAG Service",
        add_help=False  # We handle help ourselves
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Service management
    start_p = subparsers.add_parser("start")
    start_p.add_argument("--interval", type=int, default=180)
    
    stop_p = subparsers.add_parser("stop")
    restart_p = subparsers.add_parser("restart")
    status_p = subparsers.add_parser("status")
    
    logs_p = subparsers.add_parser("logs")
    logs_p.add_argument("-f", "--follow", action="store_true")
    logs_p.add_argument("-n", "--lines", type=int, default=50)
    
    # Repo management (NEW: subcommand style)
    repo_p = subparsers.add_parser("repo")
    repo_sub = repo_p.add_subparsers(dest="repo_command", required=True)
    
    add_p = repo_sub.add_parser("add")
    add_p.add_argument("path")
    
    remove_p = repo_sub.add_parser("remove")
    remove_p.add_argument("path")
    
    list_p = repo_sub.add_parser("list")
    
    # Health & diagnostics
    health_p = subparsers.add_parser("health")
    config_p = subparsers.add_parser("config")
    
    failures_p = subparsers.add_parser("failures")
    failures_sub = failures_p.add_subparsers(dest="failures_command")
    clear_p = failures_sub.add_parser("clear")
    clear_p.add_argument("--repo")
    
    # Advanced
    interval_p = subparsers.add_parser("interval")
    interval_p.add_argument("seconds", type=int)
    
    force_p = subparsers.add_parser("force-cycle")
    
    exorcist_p = subparsers.add_parser("exorcist")
    exorcist_p.add_argument("path")
    exorcist_p.add_argument("--dry-run", action="store_true")
    exorcist_p.add_argument("--force", action="store_true")
    
    # Hidden internal command for systemd
    daemon_p = subparsers.add_parser("_daemon_loop")
    daemon_p.add_argument("--interval", type=int, default=180)
    
    args = parser.parse_args(argv)
    
    # Route to handlers
    state = ServiceState()
    tracker = FailureTracker()
    
    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": cmd_status,
        "logs": cmd_logs,
        "repo": cmd_repo,
        "health": cmd_health,
        "config": cmd_config,
        "failures": cmd_failures,
        "interval": cmd_interval,
        "force-cycle": cmd_force_cycle,
        "exorcist": cmd_exorcist,
        "_daemon_loop": cmd_daemon_loop,
    }
    
    return commands[args.command](args, state, tracker)
```

#### 3.2.2 Help Screen Function
```python
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
  logs [-f]            View service logs (use -f to follow)

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

For detailed help: llmc-rag help <command>
""")
```

---

### 3.3 tools/rag/service_daemon.py (Systemd Integration)

**Purpose:** Handle all systemd-related operations.

**Design:**
```python
"""
Systemd integration for LLMC RAG Service.
"""
import os
import subprocess
from pathlib import Path
from typing import Optional

SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
SERVICE_NAME = "llmc-rag.service"


class SystemdManager:
    """Manages systemd service lifecycle."""
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.service_file = SYSTEMD_USER_DIR / SERVICE_NAME
    
    def is_systemd_available(self) -> bool:
        """Check if systemd is available on this system."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def install_service(self) -> bool:
        """Generate and install systemd service file."""
        SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
        
        llmc_rag_path = self.repo_root / "scripts" / "llmc-rag"
        
        service_content = f"""[Unit]
Description=LLMC RAG Enrichment Service
After=network.target

[Service]
Type=simple
ExecStart={llmc_rag_path} _daemon_loop
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment
Environment="PATH={os.environ.get('PATH', '')}"
Environment="PYTHONPATH={self.repo_root}"

[Install]
WantedBy=default.target
"""
        
        self.service_file.write_text(service_content)
        
        # Reload systemd
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        
        return True
    
    def start(self) -> tuple[bool, str]:
        """Start the service via systemd."""
        if not self.service_file.exists():
            if not self.install_service():
                return False, "Failed to install service file"
        
        try:
            subprocess.run(
                ["systemctl", "--user", "start", SERVICE_NAME],
                check=True,
                capture_output=True,
                text=True
            )
            return True, "Service started"
        except subprocess.CalledProcessError as e:
            return False, e.stderr
    
    def stop(self) -> tuple[bool, str]:
        """Stop the service via systemd."""
        try:
            subprocess.run(
                ["systemctl", "--user", "stop", SERVICE_NAME],
                check=True,
                capture_output=True,
                text=True
            )
            return True, "Service stopped"
        except subprocess.CalledProcessError as e:
            return False, e.stderr
    
    def restart(self) -> tuple[bool, str]:
        """Restart the service via systemd."""
        try:
            subprocess.run(
                ["systemctl", "--user", "restart", SERVICE_NAME],
                check=True,
                capture_output=True,
                text=True
            )
            return True, "Service restarted"
        except subprocess.CalledProcessError as e:
            return False, e.stderr
    
    def status(self) -> dict:
        """Get service status from systemd."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "status", SERVICE_NAME],
                capture_output=True,
                text=True
            )
            
            # Parse systemctl status output
            is_active = "Active: active" in result.stdout
            is_running = is_active and "running" in result.stdout
            
            # Extract PID if running
            pid = None
            for line in result.stdout.split("\n"):
                if "Main PID:" in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            pid = int(parts[2])
                        except ValueError:
                            pass
            
            return {
                "running": is_running,
                "active": is_active,
                "pid": pid,
                "status_text": result.stdout
            }
        except Exception as e:
            return {
                "running": False,
                "active": False,
                "pid": None,
                "error": str(e)
            }
    
    def enable(self) -> tuple[bool, str]:
        """Enable service to start on boot."""
        try:
            subprocess.run(
                ["systemctl", "--user", "enable", SERVICE_NAME],
                check=True,
                capture_output=True,
                text=True
            )
            return True, "Service enabled for boot"
        except subprocess.CalledProcessError as e:
            return False, e.stderr
    
    def disable(self) -> tuple[bool, str]:
        """Disable service from starting on boot."""
        try:
            subprocess.run(
                ["systemctl", "--user", "disable", SERVICE_NAME],
                check=True,
                capture_output=True,
                text=True
            )
            return True, "Service disabled"
        except subprocess.CalledProcessError as e:
            return False, e.stderr
    
    def get_logs(self, lines: int = 50, follow: bool = False) -> Optional[subprocess.Popen]:
        """Get logs via journalctl."""
        cmd = ["journalctl", "--user", "-u", SERVICE_NAME, "-n", str(lines)]
        
        if follow:
            cmd.append("-f")
            # Return process handle for streaming
            return subprocess.Popen(cmd)
        else:
            # Return output directly
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout)
            return None
```

**Key Decisions:**
- Service file generated automatically with correct paths
- Uses systemd journal for logging (accessed via journalctl)
- Handles missing systemd gracefully (fallback to fork() mode)
- Auto-reload daemon after service file changes

---

### 3.4 tools/rag/service_health.py (Health Checks)

**Purpose:** Check Ollama endpoint availability.

**Design:**
```python
"""
Health checking for LLMC RAG Service.
"""
import json
import urllib.request
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class OllamaEndpoint:
    """Represents an Ollama endpoint."""
    label: str
    url: str
    model: str  # Model to test with


@dataclass
class HealthStatus:
    """Health check result for an endpoint."""
    endpoint: OllamaEndpoint
    reachable: bool
    latency_ms: float
    error: str = ""


class HealthChecker:
    """Performs health checks on Ollama endpoints."""
    
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
    
    def check_endpoint(self, endpoint: OllamaEndpoint) -> HealthStatus:
        """Ping an Ollama endpoint with minimal request."""
        import time
        
        start = time.time()
        
        payload = json.dumps({
            "model": endpoint.model,
            "prompt": "ping",
            "stream": False
        }).encode("utf-8")
        
        req = urllib.request.Request(
            f"{endpoint.url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                _ = resp.read(1)  # Just check we got bytes back
            
            latency_ms = (time.time() - start) * 1000
            return HealthStatus(
                endpoint=endpoint,
                reachable=True,
                latency_ms=latency_ms
            )
        
        except Exception as e:
            return HealthStatus(
                endpoint=endpoint,
                reachable=False,
                latency_ms=0,
                error=str(e)
            )
    
    def check_all(self, endpoints: List[OllamaEndpoint]) -> List[HealthStatus]:
        """Check all endpoints."""Check all endpoints."""
        return [self.check_endpoint(ep) for ep in endpoints]
    
    def format_results(self, results: List[HealthStatus]) -> str:
        """Format health check results for display."""
        output = []
        output.append("LLMC RAG Health Check")
        output.append("=" * 50)
        output.append("")
        
        reachable = [r for r in results if r.reachable]
        unreachable = [r for r in results if not r.reachable]
        
        if reachable:
            output.append("✅ Reachable Endpoints:")
            for r in reachable:
                output.append(f"  {r.endpoint.label:15} {r.endpoint.url:40} ({r.latency_ms:.0f}ms)")
        
        if unreachable:
            output.append("")
            output.append("❌ Unreachable Endpoints:")
            for r in unreachable:
                output.append(f"  {r.endpoint.label:15} {r.endpoint.url:40}")
                output.append(f"    Error: {r.error}")
        
        output.append("")
        output.append(f"Summary: {len(reachable)}/{len(results)} endpoints healthy")
        
        return "\n".join(output)


def parse_ollama_hosts_from_env() -> List[OllamaEndpoint]:
    """Parse ENRICH_OLLAMA_HOSTS environment variable."""
    import os
    
    raw = os.getenv("ENRICH_OLLAMA_HOSTS", "")
    if not raw:
        return []
    
    endpoints = []
    model = os.getenv("ENRICH_MODEL", "qwen2.5:7b-instruct")
    
    for chunk in raw.split(","):
        part = chunk.strip()
        if not part:
            continue
        
        if "=" in part:
            label, url = part.split("=", 1)
        else:
            label, url = "", part
        
        label = label.strip() or f"host{len(endpoints) + 1}"
        url = url.strip()
        
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"
        
        endpoints.append(OllamaEndpoint(
            label=label,
            url=url.rstrip("/"),
            model=model
        ))
    
    return endpoints
```

---

### 3.5 tools/rag/service_exorcist.py (Database Nuke)

**Purpose:** Nuclear option to completely rebuild RAG database.

**Design:**
```python
"""
Exorcist command: Nuclear database rebuild.
"""
import os
import shutil
import time
from pathlib import Path
from typing import Dict, List


class ExorcistStats:
    """Statistics about what will be deleted."""
    
    def __init__(self, repo: Path):
        self.repo = repo
        self.rag_dir = repo / ".rag"
        
        self.index_db = self.rag_dir / "rag_index.db"
        self.enrichments = self.rag_dir / "enrichments.json"
        self.embeddings_db = self.rag_dir / "embeddings.db"
        self.quality_dir = self.rag_dir / "quality_reports"
        self.failures_db = self.rag_dir / "failures.db"
    
    def gather(self) -> Dict:
        """Gather statistics about what exists."""
        stats = {
            "exists": self.rag_dir.exists(),
            "files": [],
            "total_size_bytes": 0,
            "span_count": 0,
            "enrichment_count": 0,
            "embedding_count": 0,
        }
        
        if not stats["exists"]:
            return stats
        
        # Index database
        if self.index_db.exists():
            size = self.index_db.stat().st_size
            stats["files"].append({
                "path": str(self.index_db.relative_to(self.repo)),
                "size_bytes": size
            })
            stats["total_size_bytes"] += size
            
            # Count spans in index
            try:
                import sqlite3
                conn = sqlite3.connect(self.index_db)
                cursor = conn.execute("SELECT COUNT(*) FROM spans")
                stats["span_count"] = cursor.fetchone()[0]
                conn.close()
            except Exception:
                pass
        
        # Enrichments JSON
        if self.enrichments.exists():
            size = self.enrichments.stat().st_size
            stats["files"].append({
                "path": str(self.enrichments.relative_to(self.repo)),
                "size_bytes": size
            })
            stats["total_size_bytes"] += size
            
            # Count enrichments
            try:
                import json
                data = json.loads(self.enrichments.read_text())
                stats["enrichment_count"] = len(data)
            except Exception:
                pass
        
        # Embeddings database
        if self.embeddings_db.exists():
            size = self.embeddings_db.stat().st_size
            stats["files"].append({
                "path": str(self.embeddings_db.relative_to(self.repo)),
                "size_bytes": size
            })
            stats["total_size_bytes"] += size
            
            # Count embeddings
            try:
                import sqlite3
                conn = sqlite3.connect(self.embeddings_db)
                cursor = conn.execute("SELECT COUNT(*) FROM embeddings")
                stats["embedding_count"] = cursor.fetchone()[0]
                conn.close()
            except Exception:
                pass
        
        # Quality reports
        if self.quality_dir.exists():
            for file in self.quality_dir.rglob("*"):
                if file.is_file():
                    size = file.stat().st_size
                    stats["files"].append({
                        "path": str(file.relative_to(self.repo)),
                        "size_bytes": size
                    })
                    stats["total_size_bytes"] += size
        
        # Failures database
        if self.failures_db.exists():
            size = self.failures_db.stat().st_size
            stats["files"].append({
                "path": str(self.failures_db.relative_to(self.repo)),
                "size_bytes": size
            })
            stats["total_size_bytes"] += size
        
        return stats


class Exorcist:
    """Handles nuclear database rebuild."""
    
    def __init__(self, repo: Path):
        self.repo = repo
        self.stats = ExorcistStats(repo)
    
    def print_warning(self, stats: Dict):
        """Print DC's safety ritual."""
        repo_name = self.repo.name
        total_mb = stats["total_size_bytes"] / (1024 * 1024)
        
        print("\n🔥 EXORCIST MODE 🔥")
        print("━" * 60)
        print("\nHey. We need to talk about what you're about to do.")
        print(f"\nYou're about to nuke the RAG database for:")
        print(f"  📁 {self.repo}")
        print("\nHere's what that means:")
        print(f"  • {stats['span_count']:,} indexed code spans - gone")
        print(f"  • {stats['enrichment_count']:,} enriched summaries - months of LLM work, vaporized")
        print(f"  • {stats['embedding_count']:,} embeddings - all that vector magic, deleted")
        print(f"  • Every quality metric, every failure you've tracked - wiped")
        print(f"  • Total: {total_mb:.1f} MB of data")
        print("\nThis is the nuclear option. There's no undo button.")
        print("\nI get it - sometimes you need to burn it down and start fresh.")
        print("If there's a spider in there or something, I understand.")
        print("Sometimes nukes from orbit are the only way to be sure.")
        print("\nBut I care about you not shooting yourself in the foot here.")
        print("\nYou've got 5 seconds to hit Ctrl+C and walk away.")
        print("After that, it's gone for good.\n")
    
    def countdown(self):
        """5-second countdown with Ctrl+C escape."""
        try:
            for i in range(5, 0, -1):
                print(f"Starting in {i}...")
                time.sleep(1)
            print()
        except KeyboardInterrupt:
            print("\n\n✅ Aborted. Nothing was deleted.")
            return False
        return True
    
    def confirm_repo_name(self) -> bool:
        """Require user to type repo name."""
        repo_name = self.repo.name
        print(f"Alright. Type the repo name to prove you mean it: {repo_name}")
        
        try:
            user_input = input("> ").strip()
            if user_input == repo_name:
                return True
            else:
                print(f"\n❌ Input '{user_input}' doesn't match '{repo_name}'")
                print("Aborting. Nothing was deleted.")
                return False
        except (KeyboardInterrupt, EOFError):
            print("\n\n✅ Aborted. Nothing was deleted.")
            return False
    
    def nuke(self, dry_run: bool = False) -> bool:
        """Perform the actual deletion."""
        rag_dir = self.repo / ".rag"
        
        if not rag_dir.exists():
            print(f"\n❌ No RAG database found at {rag_dir}")
            print("Nothing to exorcise.")
            return False
        
        if dry_run:
            print("\n🔍 DRY RUN - Would delete:")
            for file in self.stats.gather()["files"]:
                print(f"  {file['path']} ({file['size_bytes'] / (1024*1024):.1f} MB)")
            print("\nNo files were actually deleted (dry run mode)")
            return True
        
        print("\n✅ Confirmed. Nuking from orbit...")
        
        # Delete specific files/dirs
        deleted = []
        
        if self.stats.index_db.exists():
            size_mb = self.stats.index_db.stat().st_size / (1024 * 1024)
            self.stats.index_db.unlink()
            print(f"🗑️  Deleted .rag/rag_index.db ({size_mb:.1f} MB)")
            deleted.append("index_db")
        
        if self.stats.enrichments.exists():
            self.stats.enrichments.unlink()
            print(f"🗑️  Deleted .rag/enrichments.json")
            deleted.append("enrichments")
        
        if self.stats.embeddings_db.exists():
            self.stats.embeddings_db.unlink()
            print(f"🗑️  Deleted .rag/embeddings.db")
            deleted.append("embeddings")
        
        if self.stats.quality_dir.exists():
            shutil.rmtree(self.stats.quality_dir)
            print(f"🗑️  Deleted .rag/quality_reports/")
            deleted.append("quality_reports")
        
        if self.stats.failures_db.exists():
            self.stats.failures_db.unlink()
            print(f"🗑️  Deleted .rag/failures.db")
            deleted.append("failures")
        
        print("\n✅ Database exorcised. She's clean.")
        print("\nWant to rebuild? Run: llmc-rag force-cycle")
        
        return True
    
    def execute(self, dry_run: bool = False, force: bool = False) -> int:
        """Full exorcist ritual."""
        # Gather stats
        stats = self.stats.gather()
        
        if not stats["exists"]:
            print(f"\n❌ No RAG database found at {self.repo / '.rag'}")
            print("Nothing to exorcise.")
            return 1
        
        if stats["span_count"] == 0 and stats["enrichment_count"] == 0:
            print(f"\nℹ️  RAG database exists but is empty.")
            print("Proceeding with cleanup...")
        
        # If force flag, skip ritual
        if force:
            return 0 if self.nuke(dry_run) else 1
        
        # The Ritual
        self.print_warning(stats)
        
        if not self.countdown():
            return 1
        
        if not self.confirm_repo_name():
            return 1
        
        return 0 if self.nuke(dry_run) else 1
```

---

## 4. Command Implementations

### 4.1 cmd_start()
```python
def cmd_start(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Start the service via systemd."""
    repo_root = Path(__file__).resolve().parents[2]
    systemd = SystemdManager(repo_root)
    
    if not systemd.is_systemd_available():
        print("❌ Systemd not available on this system")
        print("Falling back to fork() mode...")
        # Fall back to old fork() implementation
        return cmd_start_fork(args, state, tracker)
    
    if not state.state["repos"]:
        print("❌ No repos registered. Use 'llmc-rag repo add' first.")
        return 1
    
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
    if success:
        print(f"🚀 {message}")
        print(f"   Tracking {len(state.state['repos'])} repos")
        print(f"   Interval: {args.interval}s")
        print(f"\n📋 View logs: llmc-rag logs -f")
        return 0
    else:
        print(f"❌ Failed to start: {message}")
        return 1
```

### 4.2 cmd_logs()
```python
def cmd_logs(args, state: ServiceState, tracker: FailureTracker) -> int:
    """View service logs."""
    repo_root = Path(__file__).resolve().parents[2]
    systemd = SystemdManager(repo_root)
    
    if not systemd.is_systemd_available():
        # Fallback to file-based logs
        log_file = Path.home() / ".llmc" / "logs" / "rag-daemon" / "rag-service.log"
        if not log_file.exists():
            print(f"❌ Log file not found: {log_file}")
            return 1
        
        if args.follow:
            import subprocess
            subprocess.run(["tail", "-f", "-n", str(args.lines), str(log_file)])
        else:
            subprocess.run(["tail", "-n", str(args.lines), str(log_file)])
        return 0
    
    # Use systemd logs
    process = systemd.get_logs(lines=args.lines, follow=args.follow)
    
    if process and args.follow:
        try:
            process.wait()
        except KeyboardInterrupt:
            process.terminate()
            print("\n")
    
    return 0
```

### 4.3 cmd_health()
```python
def cmd_health(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Check Ollama endpoint health."""
    from tools.rag.service_health import (
        HealthChecker,
        parse_ollama_hosts_from_env
    )
    
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
```

### 4.4 cmd_exorcist()
```python
def cmd_exorcist(args, state: ServiceState, tracker: FailureTracker) -> int:
    """Nuclear option: rebuild RAG database."""
    from tools.rag.service_exorcist import Exorcist
    
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
    return exorcist.execute(dry_run=args.dry_run, force=args.force)
```

---

## 5. Data Flow

### 5.1 Service Start Flow
```
User: llmc-rag start
  └─> scripts/llmc-rag
       └─> tools/rag/service.py::main()
            └─> cmd_start()
                 ├─> Check systemd available
                 ├─> SystemdManager.install_service()
                 │    └─> Generate ~/.config/systemd/user/llmc-rag.service
                 ├─> systemctl --user start llmc-rag
                 └─> Systemd spawns: llmc-rag _daemon_loop
                      └─> tools/rag/service.py::cmd_daemon_loop()
                           └─> RAGService.run_loop()
                                ├─> For each repo:
                                │    └─> process_repo()
                                │         ├─> run_sync() (runner.py)
                                │         ├─> run_enrich() (runner.py)
                                │         │    └─> qwen_enrich_batch.py
                                │         │         └─> SACRED LOGGING (line 1994)
                                │         ├─> run_embed() (runner.py)
                                │         └─> run_quality_check()
                                └─> Sleep interval, repeat
```

### 5.2 Logs Flow
```
User: llmc-rag logs -f
  └─> scripts/llmc-rag
       └─> tools/rag/service.py::main()
            └─> cmd_logs()
                 └─> SystemdManager.get_logs(follow=True)
                      └─> journalctl --user -u llmc-rag -f
                           └─> Streams output from service
                                └─> Shows enrichment logs in real-time
```

### 5.3 Exorcist Flow
```
User: llmc-rag exorcist /home/you/src/llmc
  └─> scripts/llmc-rag
       └─> tools/rag/service.py::main()
            └─> cmd_exorcist()
                 ├─> Check service not running
                 ├─> Exorcist.gather_stats()
                 ├─> print_warning() (DC's ritual)
                 ├─> countdown() (5 seconds, Ctrl+C escape)
                 ├─> confirm_repo_name()
                 └─> nuke()
                      ├─> Delete .rag/rag_index.db
                      ├─> Delete .rag/enrichments.json
                      ├─> Delete .rag/embeddings.db
                      └─> Delete .rag/quality_reports/
```

---

## 6. Error Handling Strategy

### 6.1 Graceful Degradation
- Systemd not available → Fall back to fork() mode
- Ollama endpoints down → Log warning, continue with available endpoints
- Single repo fails → Log error, continue with other repos

### 6.2 User-Friendly Error Messages
```python
# BAD
raise Exception("Permission denied")

# GOOD
print("❌ Cannot access RAG database")
print("\nPossible causes:")
print("  • Database file locked by another process")
print("  • Insufficient permissions")
print("\nTry:")
print("  llmc-rag stop")
print("  Check file permissions on .rag/rag_index.db")
return 1
```

### 6.3 Critical Failures
Service will **refuse to start** if:
- No repos registered
- State file unwritable
- Python environment broken

Service will **log and continue** for:
- Single repo errors
- Ollama endpoint failures
- Quality check failures

---

## 7. Testing Plan

### 7.1 Unit Tests
```python
# tests/test_service_exorcist.py
def test_exorcist_stats_gathering():
    """Test stats collection from .rag directory."""
    ...

def test_exorcist_dry_run():
    """Test --dry-run doesn't actually delete."""
    ...

def test_exorcist_abort_on_running_service():
    """Test exorcist refuses when service is running."""
    ...

# tests/test_service_health.py
def test_health_check_reachable_endpoint():
    """Test health check on working Ollama."""
    ...

def test_health_check_unreachable_endpoint():
    """Test health check handles timeout."""
    ...

# tests/test_systemd_manager.py
def test_generate_service_file():
    """Test systemd service file generation."""
    ...

def test_systemd_not_available():
    """Test graceful fallback when systemd missing."""
    ...
```

### 7.2 Integration Tests
```bash
# Test full workflow
llmc-rag repo add /tmp/test-repo
llmc-rag health
llmc-rag start
sleep 30
llmc-rag logs | grep "Stored enrichment"
llmc-rag status
llmc-rag stop
llmc-rag exorcist /tmp/test-repo --dry-run
```

### 7.3 Logging Verification (CRITICAL)
```bash
# Before changes
cd /home/vmlinux/src/llmc
./scripts/llmc-rag-service start
tail -f ~/.llmc/logs/rag-daemon/rag-service.log > /tmp/old-logs.txt

# After changes
llmc-rag start
llmc-rag logs -f > /tmp/new-logs.txt

# Compare (must be identical except timestamps)
diff -u /tmp/old-logs.txt /tmp/new-logs.txt
```

---

## 8. Migration Path

### 8.1 Backwards Compatibility
```bash
# Keep old command as symlink
ln -s llmc-rag scripts/llmc-rag-service
```

### 8.2 User Migration
1. Existing service running → `scripts/llmc-rag-service stop`
2. Install new CLI → `git pull`
3. Start new service → `llmc-rag start`
4. Old state/repos migrate automatically

### 8.3 Rollback Plan
```bash
git revert <commit-hash>
systemctl --user stop llmc-rag
rm ~/.config/systemd/user/llmc-rag.service
systemctl --user daemon-reload
scripts/llmc-rag-service start  # Old fork() mode
```

---

## 9. Performance Considerations

### 9.1 Startup Time
- Service file generation: <100ms
- Systemd start: ~1-2 seconds
- First enrichment cycle: Variable (depends on pending spans)

### 9.2 Memory Usage
- Base service: ~50MB Python process
- During enrichment: +200MB per Ollama request
- Total: ~300MB typical, 500MB peak

### 9.3 Disk Usage
- Service logs: Managed by systemd (automatic rotation)
- State files: <1KB
- RAG databases: Unchanged from current implementation

---

## 10. Implementation Checklist

### Phase 1: Systemd Integration
- [ ] Create `tools/rag/service_daemon.py`
- [ ] Implement `SystemdManager` class
- [ ] Add `_daemon_loop` hidden command
- [ ] Update `cmd_start()` to use systemd
- [ ] Update `cmd_stop()` to use systemd
- [ ] Implement `cmd_restart()`
- [ ] Test systemd integration

### Phase 2: Health & Logs
- [ ] Create `tools/rag/service_health.py`
- [ ] Implement `HealthChecker` class
- [ ] Implement `cmd_health()`
- [ ] Implement `cmd_logs()`
- [ ] Implement `cmd_config()`
- [ ] Test all health/diagnostic commands

### Phase 3: Exorcist
- [ ] Create `tools/rag/service_exorcist.py`
- [ ] Implement `ExorcistStats` class
- [ ] Implement `Exorcist` class with DC's ritual
- [ ] Implement `cmd_exorcist()`
- [ ] Test dry-run mode
- [ ] Test full nuke + rebuild
- [ ] Verify safety checks work

### Phase 4: Polish
- [ ] Implement beautiful help screen
- [ ] Refactor repo commands (add/remove/list)
- [ ] Implement `cmd_interval()`
- [ ] Implement `cmd_force_cycle()`
- [ ] Add per-command help
- [ ] Input validation
- [ ] Error message improvements

### Phase 5: Testing
- [ ] Write unit tests for each new module
- [ ] Integration test: full workflow
- [ ] **CRITICAL:** Verify logging unchanged
- [ ] Test systemd fallback to fork() mode
- [ ] Test exorcist Ctrl+C abort
- [ ] Performance testing

### Phase 6: Documentation
- [ ] Update README with new CLI
- [ ] Write migration guide
- [ ] Systemd troubleshooting guide
- [ ] Add examples for each command

---

## 11. Open Implementation Questions

1. **Fork() fallback complexity?**
   - Keep minimal fork() mode for non-systemd systems?
   - Or require systemd and document alternatives?

2. **Log file preservation?**
   - Keep writing to ~/.llmc/logs/rag-daemon/*.log alongside journalctl?
   - Or journalctl only?

3. **State file location?**
   - Keep ~/.llmc/rag-service.json?
   - Or move to XDG-compliant ~/.config/llmc/?

4. **Exorcist --force flag?**
   - Skip ritual entirely for scripting?
   - Or always require human confirmation?

5. **Auto-enable on first start?**
   - `llmc-rag start` should also enable boot persistence?
   - Or separate `llmc-rag enable` command?

---

## 12. Success Metrics

✅ **Functional:**
- All commands work as specified
- Systemd integration stable
- Exorcist ritual prevents accidents
- Health checks detect real issues

✅ **User Experience:**
- Help screen is beautiful and useful
- Error messages are friendly and actionable
- No user confusion about which command to use
- Logs are readable and informative

✅ **Technical:**
- LOGGING FORMAT EXACTLY UNCHANGED
- No performance regression
- Clean code organization
- Comprehensive test coverage
- Graceful error handling

✅ **Emotional (DC's telescope):**
- DC can watch his matrix screen
- Enrichment logs flow perfectly
- No wasted days, no rollbacks
- The app has DC's personality in it

---

**Status:** DRAFT - Awaiting DC approval before implementation

**Next:** DC reviews SDD, provides feedback on:
- Module designs
- Command implementations
- Error handling approach
- Testing strategy
- Open implementation questions
