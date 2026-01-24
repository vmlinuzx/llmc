# Repository Context Summary Notes

- **Source:** `/home/vmlinux/Downloads/Repository Context Summary.pdf`
- **Ingested:** 2025-11-05

## Overview
- LLM Commander is a reusable template that wires local-first RAG pipelines, enrichment scripts, and multi-agent orchestration (Codex, Claude, Gemini) to keep assistants context-aware.
- Manual workflows (`rag_refresh.sh`, `rag_sync.sh`) currently power RAG updates but require developers to remember to run them.
- The roadmap calls for “Automate RAG freshness (hourly or on-change)” so `.rag/index.db` mirrors repository changes without manual effort.

## Key Requirements Highlighted
- **Freshness cadence:** Support scheduled (e.g., hourly) and on-change refresh strategies, ideally configurable per project.
- **Scalability:** Solution must scale to dozens of projects with minimal per-project babysitting or resource contention.
- **Reliability:** Handle failures gracefully, avoid stale indexes, and prevent runaway CPU usage when many refreshes run concurrently.
- **Environment fit:** Target Linux/macOS dev environments; cron is acceptable, but documentable fallback is needed for systems lacking it.

## Proposed Automations
- **Cron-first approach:** Install a cron entry that calls a wrapper around `scripts/rag_refresh.sh`, ensuring environment variables (`PYTHON_BIN`, `LLMC_RAG_INDEX_PATH`, auth keys) are exported inside the script.
- **Loop wrapper:** Offer a background loop (`start_rag_refresh_loop.sh`) for developers who prefer a persistent watcher; add locking to avoid overlapping runs.
- **Locking & logging:** Use a lock file in `.rag/` or `/tmp` so only one refresh runs at a time; append logs to `logs/rag_refresh.log` for observability.
- **Config knobs:** Allow overrides via env vars (interval, batch size, cooldown) and document sensible defaults to balance freshness vs. compute load.

## Implementation Notes
- `rag_refresh.sh` already skips syncing when `git status` reports no tracked changes, so the automation can exit early without re-enrichment when nothing changed.
- To reduce unnecessary load, consider short-circuiting the enrichment step when `rag_sync.sh` has no work.
- Provide setup docs walking developers through enabling cron, verifying permissions, and checking the log file.
- Future enhancements include Git hooks, CI-based refreshes, or dedicated daemons, but cron automation satisfies current roadmap priorities.

