# RAG Freshness Automation

Last updated: 2025-11-05

## Goal
Keep `.rag/index.db` and enrichment artifacts up to date without manual `rag_refresh.sh` runs.

## Cron-Oriented Workflow
- Use `llmc refresh` (wrapper for `scripts/rag_refresh_cron.sh`) as the entry point for scheduled refreshes; it wraps `rag_refresh.sh` with logging and a non-blocking lock so overlapping jobs exit cleanly.
- Default locations:
  - Lock file: `.rag/rag_refresh.lock` (`RAG_REFRESH_LOCK_FILE` override)
  - Log file: `logs/rag_refresh.log` (`RAG_REFRESH_LOG_FILE` override)
- Each invocation also calls `scripts/deep_research_ingest.sh` to pull notes from `research/incoming/` into `DOCS/RESEARCH/Deep_Research/` and re-index them automatically.
- Recommended hourly cron on Linux/macOS:
  ```cron
  # m h dom mon dow command
  0 * * * * llmc --repo /path/to/repo refresh
  ```
- Export credentials and env vars inside the crontab if embeddings require them (e.g., `PYTHON_BIN`, `LLMC_RAG_INDEX_PATH`, API keys).

## Tunable Environment Flags
- `RAG_REFRESH_FORCE=1` — run full pipeline even when git has no tracked changes (otherwise the script exits early).
- `RAG_REFRESH_SKIP_ENRICH=1` — skip the enrichment batch (useful for light refresh or testing).
- `RAG_REFRESH_SKIP_EMBED=1` — skip re-embedding.
- `RAG_REFRESH_SKIP_STATS=1` — skip the stats summary.
- `RAG_REFRESH_BATCH_SIZE`, `RAG_REFRESH_COOLDOWN`, `RAG_REFRESH_EMBED_LIMIT` — threading knobs forwarded to the existing scripts.

## Loop-Based Alternative
- For a persistent watcher, reuse `scripts/start_rag_refresh_loop.sh` (default interval 3600s). Launch it via tmux/systemd if continuous background execution is desired.
- Example tmux launch:
  ```bash
  ./scripts/run_in_tmux.sh -s rag-refresh --timeout 0 -- ./scripts/start_rag_refresh_loop.sh
  ```

## Verification
- For manual smoke tests without the heavy enrichment step:
  ```bash
  RAG_REFRESH_SKIP_ENRICH=1 RAG_REFRESH_SKIP_EMBED=1 RAG_REFRESH_SKIP_STATS=1 llmc --repo /path/to/repo refresh
  ```
- Logs accumulate in `logs/rag_refresh.log`; review for failures or skipped runs.

## Manual Deep Research Intake
- Drop Markdown notes (plus optional attachments) into `research/incoming/`. Use `research/deep_research_notes.template.md` as a starting point.
- `scripts/deep_research_ingest.sh` (or `llmc --repo /path/to/repo ingest`) moves new files into `DOCS/RESEARCH/Deep_Research/` (attachments land in the `assets/` subfolder) and calls `rag_sync.sh` so the knowledge base sees the update.
- Run `llmc --repo /path/to/repo ingest --dry-run` to preview moves; it is invoked automatically by `llmc refresh`.
