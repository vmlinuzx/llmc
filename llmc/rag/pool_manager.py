import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Fallback for < 3.9 if needed

import httpx

from llmc.rag.pool_config import PoolConfig, WorkerConfig, parse_schedule_to_minutes

log = logging.getLogger(__name__)

@dataclass
class WorkerState:
    config: WorkerConfig
    process: subprocess.Popen | None = None
    status: str = "stopped"  # stopped, running, failed, dead
    pid: int | None = None
    restarts: int = 0
    start_time: float = 0.0
    last_error: str | None = None
    consecutive_failures: int = 0
    health_status: str = "unknown"  # unknown, healthy, unhealthy
    last_health_check: float = 0.0

class PoolManager:
    def __init__(self, config: PoolConfig, repo_root: Path):
        self.config = config
        self.repo_root = repo_root
        self.workers: dict[str, WorkerState] = {}
        self.running = False
        self.status_file = repo_root / ".llmc" / "tmp" / "pool_status.json"
        
        # Ensure tmp dir exists
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize registry
        for w in self.config.workers:
            self.workers[w.id] = WorkerState(config=w)

    def _update_status_file(self):
        """Writes current pool status to disk for the debug command."""
        status_data: dict[str, Any] = {
            "running": self.running,
            "workers": {}
        }
        for w_id, state in self.workers.items():
            status_data["workers"][w_id] = {
                "status": state.status,
                "pid": state.pid,
                "restarts": state.restarts,
                "uptime": time.time() - state.start_time if state.status == "running" else 0,
                "type": state.config.type,
                "model": state.config.model,
                "health_status": state.health_status,
                "consecutive_failures": state.consecutive_failures,
                "last_health_check": state.last_health_check,
                "schedule": state.config.schedule,
                "schedule_active": self._is_within_schedule(state.config) if state.config.schedule else True
            }
        
        try:
            with open(self.status_file, "w") as f:
                json.dump(status_data, f, indent=2)
        except Exception as e:
            log.error(f"Failed to write status file: {e}")

    def _is_within_schedule(self, config: WorkerConfig) -> bool:
        """
        Checks if the current time is within the worker's schedule.
        Schedule format: "HH:MM-HH:MM" (e.g. "09:00-17:00" or "22:00-06:00").
        """
        if not config.schedule:
            return True

        try:
            tz = ZoneInfo(config.schedule_timezone)
            now = datetime.now(tz)
            
            start_minutes, end_minutes = parse_schedule_to_minutes(config.schedule)
            
            # Convert to minutes from midnight for easier comparison
            current_minutes = now.hour * 60 + now.minute
            
            if start_minutes <= end_minutes:
                # Standard schedule (e.g., 09:00-17:00)
                return start_minutes <= current_minutes < end_minutes
            else:
                # Overnight schedule (e.g., 22:00-06:00)
                # Active if after start OR before end
                return current_minutes >= start_minutes or current_minutes < end_minutes
                
        except Exception as e:
            log.error(f"Error parsing schedule '{config.schedule}' for worker {config.id}: {e}")
            # Fail closed for safety
            return False

    def spawn_worker(self, worker_id: str):
        state = self.workers.get(worker_id)
        if not state:
            log.error(f"Worker {worker_id} not found in config")
            return

        if not state.config.enabled:
            return
            
        # Check schedule
        if not self._is_within_schedule(state.config):
            log.info(f"Worker {worker_id} not spawned: outside schedule {state.config.schedule}")
            return

        # Use pool_worker.py with environment variables for backend config
        # This bypasses the router and calls the assigned Ollama server directly
        cmd = [
            sys.executable,
            "-m", "llmc.rag.pool_worker",
        ]
        
        # Build environment with worker config
        env = os.environ.copy()
        env["LLMC_WORKER_ID"] = worker_id
        env["LLMC_WORKER_HOST"] = state.config.host
        env["LLMC_WORKER_PORT"] = str(state.config.port)
        env["LLMC_WORKER_MODEL"] = state.config.model
        env["LLMC_WORKER_TIER"] = str(state.config.tier)
        env["LLMC_MAX_TIER"] = str(self.config.max_tier)
        
        try:
            log.info(f"Spawning pool worker {worker_id} -> {state.config.host}:{state.config.port}")
            # Redirecting stdout/stderr to files for debugging
            log_dir = self.repo_root / ".llmc" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            stdout_path = log_dir / f"worker_{worker_id}.out"
            stderr_path = log_dir / f"worker_{worker_id}.err"
            
            stdout_file = open(stdout_path, "a")
            stderr_file = open(stderr_path, "a")

            process = subprocess.Popen(
                cmd,
                cwd=str(self.repo_root),
                env=env,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True
            )
            state.process = process
            state.pid = process.pid
            state.status = "running"
            state.start_time = time.time()
            # Reset health metrics on new spawn
            state.consecutive_failures = 0
            state.health_status = "unknown"
            
            stdout_file.close()
            stderr_file.close()

        except Exception as e:
            log.error(f"Failed to spawn worker {worker_id}: {e}")
            state.status = "failed"
            state.last_error = str(e)

        self._update_status_file()

    def stop_worker(self, worker_id: str):
        state = self.workers.get(worker_id)
        if not state:
            return

        if not state.process:
            state.status = "stopped" # Ensure status is updated even if process object is gone
            state.pid = None
            state.health_status = "unknown"
            self._update_status_file()
            return

        if state.process.poll() is not None:
            state.status = "stopped"
            state.process = None
            state.pid = None
            state.health_status = "unknown"
            self._update_status_file()
            return

        log.info(f"Stopping worker {worker_id} (PID {state.process.pid})")
        state.process.terminate()
        
        try:
            # AC-3.6: Graceful drain. Worker handles SIGTERM.
            # We wait 10s to allow for a reasonable drain time.
            state.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            log.warning(f"Worker {worker_id} did not stop, killing...")
            state.process.kill()
            state.process.wait()
            
        state.status = "stopped"
        state.process = None
        state.pid = None
        state.health_status = "unknown"
        self._update_status_file()

    async def check_worker_health(self, worker_id: str):
        """Pings the worker's Ollama API to check if it's responsive."""
        state = self.workers.get(worker_id)
        if not state or state.status != "running":
            return
            
        # If not within schedule, we shouldn't be checking health (it should be stopped)
        # But if it IS running outside schedule (race condition?), we check it.
        # Actually, if it's running, we check it.

        url = f"http://{state.config.host}:{state.config.port}/api/tags"
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                
            if response.status_code == 200:
                if state.consecutive_failures > 0:
                    log.info(f"Worker {worker_id} recovered after {state.consecutive_failures} failures.")
                state.consecutive_failures = 0
                state.health_status = "healthy"
            else:
                log.warning(f"Worker {worker_id} health check failed: HTTP {response.status_code}")
                state.consecutive_failures += 1
                
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            log.warning(f"Worker {worker_id} health check failed: {e}")
            state.consecutive_failures += 1
            
        state.last_health_check = time.time()
        
        if state.consecutive_failures >= 3:
            if state.health_status != "unhealthy":
                log.error(f"Worker {worker_id} marked UNHEALTHY after {state.consecutive_failures} consecutive failures.")
            state.health_status = "unhealthy"

    async def check_all_health(self):
        """Runs health checks for all running workers concurrently."""
        tasks = []
        for w_id in self.workers:
            tasks.append(self.check_worker_health(w_id))
        if tasks:
            await asyncio.gather(*tasks)
        self._update_status_file()

    def monitor_workers(self):
        """Check for dead workers and restart if needed. Enforce schedules."""
        for worker_id, state in self.workers.items():
            if not state.config.enabled:
                if state.status == "running":
                    self.stop_worker(worker_id)
                continue

            # AC-3.1, 3.4, 3.5: Schedule Enforcement
            in_schedule = self._is_within_schedule(state.config)
            
            if not in_schedule:
                if state.status == "running":
                    log.info(f"Worker {worker_id} stopping: outside schedule {state.config.schedule}")
                    self.stop_worker(worker_id)
                continue
            
            # If we are here, we SHOULD be running
            if state.status == "stopped" or state.status == "dead":
                 # Only auto-restart if not failed (failed means max retries exceeded)
                 # But if it was stopped due to schedule, we should restart it.
                 # How to distinguish "stopped by schedule" vs "stopped manually"?
                 # We don't have manual stop state yet.
                 # Assuming "stopped" means we can start it.
                 # But "failed" means we shouldn't.
                 if state.status != "failed":
                     self.spawn_worker(worker_id)

            if state.status == "running":
                if state.process is None:
                    state.status = "stopped"
                    continue
                
                ret_code = state.process.poll()
                if ret_code is not None:
                    log.warning(f"Worker {worker_id} died with code {ret_code}")
                    state.status = "dead"
                    state.process = None
                    state.pid = None
                    
                    if state.restarts < self.config.max_retries:
                        log.info(f"Restarting worker {worker_id} ({state.restarts + 1}/{self.config.max_retries})")
                        state.restarts += 1
                        time.sleep(1) # Backoff slightly
                        self.spawn_worker(worker_id)
                    else:
                        log.error(f"Worker {worker_id} exceeded max retries")
                        state.status = "failed"
                        state.last_error = f"Exceeded max retries (exit code {ret_code})"
        
        self._update_status_file()

    def start_all(self):
        self.running = True
        if not self.config.enabled:
            log.info("Pool is disabled in config.")
            return

        workers_by_tier = defaultdict(list)
        for w in self.config.workers:
            workers_by_tier[w.tier].append(w)

        for tier, workers in sorted(workers_by_tier.items()):
            print(f"🚀 Starting tier {tier} ({len(workers)} workers)")
            for w in workers:
                if w.enabled:
                    self.spawn_worker(w.id)
        
        self._update_status_file()

    def stop_all(self):
        self.running = False
        for w_id in self.workers:
            self.stop_worker(w_id)
        self._update_status_file()

    def _get_registered_repos(self) -> list[str]:
        """Get list of registered repo paths from daemon state."""
        state_file = Path.home() / ".llmc" / "rag_daemon_state.json"
        if not state_file.exists():
            # Fall back to repo_root if no daemon state
            return [str(self.repo_root)]
        try:
            with open(state_file) as f:
                state = json.load(f)
            return state.get("repos", [str(self.repo_root)])
        except Exception:
            return [str(self.repo_root)]

    def _feed_queue(self) -> int:
        """Feed pending enrichments from repos to work queue."""
        from llmc.rag.work_queue import feed_queue_from_repos
        repos = self._get_registered_repos()
        added = feed_queue_from_repos(repos, limit_per_repo=100)
        if added > 0:
            print(f"📥 Fed {added} items to work queue", flush=True)
        return added

    def run_loop(self):
        """Main loop for the pool manager process."""
        self.start_all()
        
        # Initial queue feed
        self._feed_queue()
        
        try:
            while self.running:
                self.monitor_workers()
                # Run async health checks
                asyncio.run(self.check_all_health())
                # Feed queue with pending enrichments
                self._feed_queue()
                time.sleep(self.config.health_check_interval)
        except KeyboardInterrupt:
            self.stop_all()
        except Exception as e:
            log.error(f"Pool manager loop crashed: {e}")
            self.stop_all()
            raise

