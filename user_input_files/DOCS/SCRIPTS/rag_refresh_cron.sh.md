# rag_refresh_cron.sh — Cron‑Safe Wrapper with Locking

Path
- scripts/rag_refresh_cron.sh

Purpose
- Run `scripts/rag_refresh.sh` from cron without overlap. Uses a non‑blocking `flock` on `.rag/rag_refresh.lock` and writes to `logs/rag_refresh.log`.

Usage
- `scripts/rag_refresh_cron.sh [--repo PATH] [options...]`
- Example cron (hourly): `0 * * * * llmc --repo /path refresh` (see DOCS/RAG_Freshness_Automation.md)

Env
- `RAG_REFRESH_LOCK_FILE`, `RAG_REFRESH_LOG_DIR`, `RAG_REFRESH_LOG_FILE`

Behavior
- Optionally ingests `research/incoming/` via `scripts/deep_research_ingest.sh` before refresh

