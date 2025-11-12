# indexenrich.sh — Index + Enrich (Local Ollama)

Path
- scripts/indexenrich.sh

Purpose
- One-shot helper to sync documented paths into `.rag/`, run enrichment locally (Ollama), and embed pending spans.

Usage
- `scripts/indexenrich.sh [--force-nano]`
- `--force-nano` uses gateway backend with `ENRICH_START_TIER=nano` to avoid VRAM limits.

Behavior
- Loads `.env.local` if present
- Verifies `tree_sitter` deps are installed; hints how to install
- Syncs known docs (e.g., `DOCS/preprocessor_flow.md`) via `tools.rag.cli sync`
- Runs `scripts/qwen_enrich_batch.py` with `--backend ollama` (or gateway when forced)
- Regenerates embeddings in small batches until no pending spans remain; prints current stats

Related
- DOCS/preprocessor_flow.md, scripts/indexenrichazure.sh, scripts/qwen_enrich_batch.py

