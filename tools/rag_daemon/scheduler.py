"""Scheduler loop for the LLMC RAG Daemon."""

from __future__ import annotations

from datetime import timedelta
import os
import random
import signal
import threading
import time

from .control import read_control_events
from .logging_utils import get_logger
from .models import DaemonConfig, Job, RepoDescriptor, RepoState, utc_now
from .registry import RegistryClient
from .state_store import StateStore
from .workers import WorkerPool, make_job_id


class Scheduler:
    """Tick-based scheduler that assigns jobs to the worker pool."""

    def __init__(
        self,
        config: DaemonConfig,
        registry: RegistryClient,
        state_store: StateStore | None,
        workers: WorkerPool,
    ) -> None:
        self.config = config
        self.registry = registry
        self.state_store = state_store or StateStore(config.state_store_path)
        self.workers = workers
        self.logger = get_logger("rag_daemon.scheduler", config)
        self._shutdown_requested = threading.Event()
        self._last_cache_cleanup = 0.0  # Track last cleanup time

    def run_forever(self) -> None:
        self._install_signal_handlers()
        self.logger.info("Starting LLMC RAG Daemon scheduler loop")

        while not self._shutdown_requested.is_set():
            start = time.time()
            try:
                self._run_tick()
            except Exception as exc:  # pragma: no cover - defensive
                self.logger.exception("Fatal error in scheduler tick: %s", exc)

            elapsed = time.time() - start
            sleep_for = max(self.config.tick_interval_seconds - elapsed, 0.0)
            sleep_for += random.uniform(0, 0.5 * self.config.tick_interval_seconds)
            if sleep_for > 0:
                time.sleep(sleep_for)

        self.logger.info("Scheduler loop exiting (shutdown requested)")

    def run_once(self) -> None:
        """Run a single scheduler tick and return.

        This is used by `llmc-rag-daemon tick` for CI/tests so that we can
        exercise scheduling logic without a long-running service loop.
        """
        try:
            self._run_tick()
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.exception("Fatal error in scheduler tick: %s", exc)

    def _install_signal_handlers(self) -> None:
        def handler(signum, frame):  # type: ignore[override]
            self.logger.info("Received signal %s, requesting shutdown", signum)
            self._shutdown_requested.set()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def _cleanup_pycache_if_needed(self) -> None:
        """Clean up old Python bytecode cache files periodically.

        Enterprise daemon behavior: prevent unbounded file accumulation
        from long-running processes by removing .pyc files older than
        the configured threshold.
        """
        # Load config from llmc.toml to get cleanup setting
        try:
            from pathlib import Path

            import tomli

            # Find repo root by walking up from this file
            repo_root = Path(__file__).parent.parent.parent.resolve()
            config_path = repo_root / "llmc.toml"

            if not config_path.exists():
                return  # No config, skip cleanup

            with open(config_path, "rb") as f:
                config = tomli.load(f)

            cleanup_days = config.get("daemon", {}).get("pycache_cleanup_days", 7)

            if cleanup_days <= 0:
                return  # Cleanup disabled

            # Only run cleanup once per day to avoid overhead
            now = time.time()
            if now - self._last_cache_cleanup < 86400:  # 24 hours
                return

            pycache_dir = repo_root / ".llmc" / "pycache"
            if not pycache_dir.exists():
                return

            cutoff_time = now - (cleanup_days * 86400)
            deleted_count = 0

            for root, dirs, files in os.walk(pycache_dir):
                for filename in files:
                    filepath = Path(root) / filename
                    try:
                        if filepath.stat().st_mtime < cutoff_time:
                            filepath.unlink()
                            deleted_count += 1
                    except (OSError, FileNotFoundError):
                        continue  # File already gone or inaccessible

            if deleted_count > 0:
                self.logger.info(
                    "Cleaned up %d .pyc files older than %d days from cache",
                    deleted_count,
                    cleanup_days,
                )

            self._last_cache_cleanup = now

        except Exception as exc:
            # Never let cleanup crash the daemon
            self.logger.warning("Failed to clean pycache: %s", exc)

    def _run_tick(self) -> None:
        # Enterprise daemon hygiene: clean up old cache files periodically
        self._cleanup_pycache_if_needed()

        now = utc_now()
        events = read_control_events(self.config.control_dir)
        if events.shutdown:
            self.logger.info("Shutdown requested via control flag")
            self._shutdown_requested.set()

        registry_entries = self.registry.load()
        states = self.state_store.load_all()
        running = self.workers.running_repo_ids()

        eligible_jobs: list[Job] = []

        for repo_id, desc in registry_entries.items():
            state = states.get(repo_id)
            if repo_id in running:
                continue

            force = events.refresh_all or (repo_id in events.refresh_repo_ids)
            if not self._is_repo_eligible(desc, state, now, force):
                continue

            job = Job(job_id=make_job_id(), repo=desc, force=force)
            eligible_jobs.append(job)

        if not eligible_jobs:
            self.logger.debug("No eligible repos this tick")
            return

        slots = max(self.config.max_concurrent_jobs - len(running), 0)
        if slots <= 0:
            self.logger.debug("Worker pool is full; deferring %d jobs", len(eligible_jobs))
            return

        to_run = eligible_jobs[:slots]
        self.logger.info("Scheduling %d RAG jobs this tick", len(to_run))
        self.workers.submit_jobs(to_run)

    def _is_repo_eligible(
        self,
        repo: RepoDescriptor,
        state: RepoState | None,
        now,
        force: bool,
    ) -> bool:
        if state is None:
            return True

        if state.last_run_status == "running" and not force:
            return False

        if state.consecutive_failures >= self.config.max_consecutive_failures and not force:
            return False

        if state.next_eligible_at and now < state.next_eligible_at and not force:
            return False

        if state.last_run_finished_at is None:
            return True

        min_interval = repo.min_refresh_interval or timedelta(
            seconds=self.config.tick_interval_seconds
        )
        if now - state.last_run_finished_at < min_interval and not force:
            return False

        return True
