# rag_refresh.sh — One‑Shot RAG Refresh

Path
- scripts/rag_refresh.sh

Purpose
- Orchestrate an incremental refresh: detect changed files → sync → enrich → embed → print stats.

Usage
- `scripts/rag_refresh.sh [--repo PATH] [options...]`

Environment toggles
- `RAG_REFRESH_FORCE=1` run even when git shows no tracked changes
- `RAG_REFRESH_SKIP_ENRICH=1` skip enrichment
- `RAG_REFRESH_SKIP_EMBED=1` skip embeddings
- `RAG_REFRESH_SKIP_STATS=1` skip stats
- `RAG_REFRESH_BATCH_SIZE`, `RAG_REFRESH_COOLDOWN`, `RAG_REFRESH_EMBED_LIMIT`

Behavior
- Chooses Python from repo `.venv`, `RAG_VENV`, exec `.venv`, else `python3`
- Detects `.rag/index_v2.db` (fallback `.rag/index.db`); exits with a hint if none exists
- Uses `scripts/rag_sync.sh` for changed paths, calls `scripts/qwen_enrich_batch.py`, then `python -m tools.rag.cli embed`, and finally `stats`

