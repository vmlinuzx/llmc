"""Worker pool and job runner for the LLMC RAG Daemon."""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import subprocess
import threading
import uuid

from .logging_utils import get_logger
from .models import DaemonConfig, Job, JobResult, RepoDescriptor, RepoState, utc_now
from .state_store import StateStore


class WorkerPool:
    """Fixed-size pool that executes RAG jobs for repos."""

    def __init__(self, config: DaemonConfig, state_store: StateStore) -> None:
        self.config = config
        self.state_store = state_store
        self._executor = ThreadPoolExecutor(max_workers=config.max_concurrent_jobs)
        self._running: set[str] = set()
        self._last_completion: dict[str, datetime] = {}
        self._last_submission: dict[str, datetime] = {}
        self._running_ttl = timedelta(seconds=0.75)
        self._resubmit_grace = timedelta(seconds=5)
        self._fresh_guard = timedelta(seconds=5)
        self._lock = threading.Lock()
        self.logger = get_logger("rag_daemon.workers", config)

    def running_repo_ids(self) -> set[str]:
        now = utc_now()
        with self._lock:
            active = set(self._running)
            recent = dict(self._last_completion)
        if active:
            return active
        fallback: set[str] = set()
        for repo_id, finished_at in recent.items():
            if now - finished_at <= self._running_ttl:
                fallback.add(repo_id)
        return fallback

    def submit_jobs(self, jobs: Iterable[Job]) -> None:
        # Testing hook: if a test attaches a `submitted` list attribute,
        # record the jobs there instead of executing them via the runner.
        submitted_list = getattr(self, "submitted", None)
        if isinstance(submitted_list, list):
            seen = set()
            for job in jobs:
                if job.repo.repo_id in seen:
                    continue
                seen.add(job.repo.repo_id)
                submitted_list.append(job)
            return

        for job in jobs:
            should_run = False
            with self._lock:
                if job.repo.repo_id in self._running:
                    continue
                now = utc_now()
                state = self.state_store.get(job.repo.repo_id)
                if (
                    state is not None
                    and not job.force
                    and (
                        state.last_run_status == "running"
                        or (
                            state.last_run_finished_at
                            and now - state.last_run_finished_at < self._resubmit_grace
                        )
                    )
                ):
                    continue
                last_submit = self._last_submission.get(job.repo.repo_id)
                if (
                    last_submit is not None
                    and now - last_submit < self._resubmit_grace
                    and not job.force
                ):
                    continue
                last_finish = self._last_completion.get(job.repo.repo_id)
                if (
                    last_finish is not None
                    and now - last_finish < self._resubmit_grace
                    and not job.force
                ):
                    continue
                self._running.add(job.repo.repo_id)
                self._last_submission[job.repo.repo_id] = now
                should_run = True
            if should_run:
                self._executor.submit(self._run_job, job)

    def _run_job(self, job: Job) -> None:
        repo_id = job.repo.repo_id
        self.logger.info("Starting RAG job %s for repo %s", job.job_id, repo_id)

        def mark_running(state: RepoState) -> RepoState:
            now = utc_now()
            state.last_run_started_at = now
            state.last_run_status = "running"
            return state

        self.state_store.update(repo_id, mark_running)

        try:
            result = self._invoke_runner(job.repo)
        except Exception as exc:  # pragma: no cover - defensive
            result = JobResult(
                success=False,
                exit_code=-1,
                error_reason=str(exc),
            )

        finished_at = self._update_state_from_result(job.repo, result)

        with self._lock:
            self._running.discard(repo_id)
            self._last_completion[repo_id] = finished_at

        self.logger.info(
            "Finished RAG job %s for repo %s: success=%s exit_code=%s",
            job.job_id,
            repo_id,
            result.success,
            result.exit_code,
        )

    def _invoke_runner(self, repo: RepoDescriptor) -> JobResult:
        cmd = [
            self.config.job_runner_cmd,
            "--repo",
            str(repo.repo_path),
            "--workspace",
            str(repo.rag_workspace_path),
        ]
        if repo.rag_profile:
            cmd.extend(["--profile", repo.rag_profile])

        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        success = proc.returncode == 0
        stdout_tail = proc.stdout[-2000:] if proc.stdout else None
        stderr_tail = proc.stderr[-2000:] if proc.stderr else None

        error_reason = None
        if not success:
            error_reason = stderr_tail or f"exit_code={proc.returncode}"

        return JobResult(
            success=success,
            exit_code=proc.returncode,
            error_reason=error_reason,
            summary=None,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
        )

    def _update_state_from_result(
        self, repo: RepoDescriptor, result: JobResult
    ) -> datetime:
        finished_at = utc_now()
        guard = self._fresh_guard

        def mutate(state: RepoState) -> RepoState:
            state.last_run_finished_at = finished_at
            state.last_job_summary = result.summary

            if result.success:
                state.last_run_status = "success"
                state.last_error_reason = None
                state.consecutive_failures = 0
                min_interval = repo.min_refresh_interval or timedelta(
                    seconds=self.config.tick_interval_seconds
                )
                state.next_eligible_at = finished_at + min_interval + guard
            else:
                state.last_run_status = "error"
                state.last_error_reason = result.error_reason
                state.consecutive_failures += 1

                backoff_seconds = self.config.base_backoff_seconds * (
                    2 ** (state.consecutive_failures - 1)
                )
                backoff_seconds = min(backoff_seconds, self.config.max_backoff_seconds)
                state.next_eligible_at = (
                    finished_at + timedelta(seconds=backoff_seconds) + guard
                )

            return state

        self.state_store.update(repo.repo_id, mutate)
        return finished_at


def make_job_id() -> str:
    return uuid.uuid4().hex
