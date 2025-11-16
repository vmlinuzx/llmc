# LLMC RAG Daemon & Repo Tool — Test Plan for Codex

This document describes **high-value tests** Codex (or another agent) should implement and run
for the LLMC RAG Daemon and Repo Registration Tool.

## 1. Daemon Config & Startup

- Load config from default path and from an explicit `--config` path.
- Failure when config file is missing or invalid YAML.
- Directories (`state_store_path`, `log_path`, `control_dir`) are created on first run.

## 2. State Store

- Round-trip of `RepoState` with and without timestamps.
- Behavior with corrupt JSON file (ignored, daemon continues).
- Atomic writes (no partially written file visible).

## 3. Registry Client

- Loading empty registry (no file).
- Loading registry with multiple entries and various `min_refresh_interval_seconds`.
- Behavior when registry contains invalid paths.

## 4. Scheduler Eligibility Logic

- Repo with no state is always eligible.
- Repo in `running` state is not eligible.
- Repo in failure with `consecutive_failures >= max_consecutive_failures` is in backoff.
- Repo with `next_eligible_at` in the future is not eligible unless forced.
- Repo whose last run is within `min_refresh_interval` is not eligible.
- Forced refresh via `refresh_<repo_id>.flag` overrides interval but not catastrophic backoff.

## 5. Control Surface

- `refresh_all.flag` leads to `refresh_all=True`.
- `refresh_<repo_id>.flag` adds that repo to `refresh_repo_ids`.
- `shutdown.flag` sets shutdown flag.
- Flags are best-effort deleted after consumption.

## 6. Worker Pool & Job Runner

- Worker marks repo `running` at job start, and updates to `success` on exit code 0.
- On non-zero exit code:
  - `last_run_status` becomes `error`.
  - `consecutive_failures` increments.
  - `next_eligible_at` reflects exponential backoff.
- Multiple jobs are limited by `max_concurrent_jobs`.

## 7. Repo Registration Tool

- `add` on new repo:
  - Creates `.llmc/rag/` workspace.
  - Writes `config/rag.yml` and `config/version.yml`.
  - Appends registry entry.
- `add` on existing workspace is idempotent (does not clobber configs).
- `list` shows registered repos (plain text and `--json`).
- `inspect` reports both workspace + registry info.
- `remove` unregisters by path and by repo_id.

## 8. End-to-End Smoke Test

- Use a temporary directory as fake `$HOME/.llmc`.
- Create a temp repo and run `llmc-rag-repo add`.
- Start a short-lived daemon instance (patched to run a single tick and terminate).
- Verify:
  - Registry has the repo.
  - State store contains a record for the repo.
  - Job runner was invoked (e.g., by injecting a dummy job_runner_cmd that logs calls).

These tests can be automated in pytest and extended with property-based testing for edge cases.
