# LLMC Integration & Scripts — Test Plan for Codex

This document describes **high-value tests** for CLI wrappers, helper scripts,
and integration glue that sit around the core RAG and daemon systems:

- Shell wrappers in `tools/` (e.g., `claude_minimax_rag_wrapper.sh`,
  `codex_rag_wrapper.sh`),
- Operational scripts in `scripts/`,
- Basic log management.

## 1. Wrapper Scripts (Codex / MiniMax / Others)

- Help & usage:
  - Running each wrapper with `--help` (or no args, if that’s the contract) prints:
    - Usage,
    - Required env vars,
    - Example invocations.
- Env var validation:
  - Missing required env vars (API keys, base URLs, model names) result in:
    - A clear error message,
    - Non-zero exit code,
    - No accidental calls with blank credentials.
- Command construction:
  - Wrapper scripts construct the underlying `llmc-rag` or service commands correctly:
    - Flags are passed through,
    - User-provided arguments are properly quoted to handle spaces/special characters.

## 2. Router & Bridge Scripts

- `scripts/router.py`:
  - Correctly routes messages/requests based on config or command-line flags.
  - Logs which backend (local, cloud, MiniMax, etc.) was chosen for each call.
  - Gracefully handles unknown routes with a clear error.
- `run_mcpo_bridge.sh` (if used):
  - Validates all required binaries and config files exist before starting.
  - Exits non-zero with a helpful message when prerequisites are missing.

## 3. RAG Operations Scripts

- `scripts/rag/index_workspace.py`:
  - Already covered in enrichment tests, but verify:
    - CLI ergonomic usage and `--help` output.
    - Safe handling of missing or misconfigured workspaces.
- `scripts/rag/query_context.py`:
  - Given a query and a repo path, returns a context bundle that:
    - Matches the RAG planner’s expectations,
    - Includes file paths, line ranges, and snippets.
  - Invalid paths or queries lead to explicit errors, not empty success.
- `scripts/rag/rag_server.py`:
  - Covered in the core service tests, but additionally:
    - Works correctly when launched via `run_in_tmux.sh` or similar helper.

## 4. Refresh / Sync / Cron Helpers

- `rag_refresh.sh` / `rag_refresh_cron.sh` / `rag_refresh_watch.sh`:
  - With a valid `$HOME/.llmc` and registry, running these scripts:
    - Triggers a refresh cycle in the daemon,
    - Leaves clear logs showing which repos were refreshed.
  - On missing config/registry:
    - They fail gracefully with actionable messages.
- `rag_sync.sh`:
  - Syncs artifacts (DB, graph, status) to the expected target (e.g., prod path or backup).
  - Detects and reports conflicts or partial syncs.

## 5. Log Management & Housekeeping

- `llmc-clean-logs.sh` / `llmc_log_manager.py`:
  - Detect log files above a configured size or age and rotate/delete them.
  - Never delete non-log files or logs outside the configured directories.
- Safety checks:
  - Scripts refuse to operate when log directories are unset or obviously wrong
    (e.g., `/` or `$HOME` directly).

## 6. Wipe & Test Harness

- `scripts/wipe_and_test.sh`:
  - In a dedicated test environment:
    - Safely wipes only the test-related artifacts (e.g., `.rag`, `.llmc` inside the repo).
    - Runs the configured pytest suite.
  - On failure:
    - Propagates the pytest exit code.
    - Prints a short summary path for detailed logs (for the Ruthless Testing Agent).

## 7. End-to-End “Operator Workflow” Scenarios

- Local dev workflow:
  - From a fresh clone:
    1. Register repo with `llmc-rag-repo`.
    2. Start daemon.
    3. Use wrapper (Codex/MiniMax) to issue a RAG-powered query.
  - Verify that all intermediate scripts behave as documented and that errors (if any)
    are actionable.
- Cron-driven refresh workflow:
  - Simulate a cron job invoking `rag_refresh_cron.sh`.
  - Confirm:
    - Daemon runs refresh jobs as expected.
    - Index status metadata and graph artifacts are updated.
    - Any failures surface clearly for classification.
