# deep_research_ingest.sh — Intake Notes and Re‑index

Path
- scripts/deep_research_ingest.sh

Purpose
- Move files from `research/incoming/` into `DOCS/RESEARCH/Deep_Research/` (non‑MD to `assets/`) with timestamped slugs, log the move, and trigger `scripts/rag_sync.sh` for any Markdown notes.

Usage
- `scripts/deep_research_ingest.sh [--repo PATH] [--dry-run]`

Outputs
- Appends to `logs/deep_research_ingest.log`. Writes ingested `.md` files under archive directory.

