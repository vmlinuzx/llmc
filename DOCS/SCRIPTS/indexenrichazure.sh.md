# indexenrichazure.sh — Index + Enrich (Azure Backend)

Path
- scripts/indexenrichazure.sh

Purpose
- Same flow as `indexenrich.sh` but forces API usage through Azure for enrichment and embeddings.

Usage
- `scripts/indexenrichazure.sh`

Required env
- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, `AZURE_OPENAI_DEPLOYMENT`
- Optional: `.env.local` is loaded automatically if present

Behavior
- Syncs selected docs → calls `scripts/qwen_enrich_batch.py --backend gateway --api --router off --start-tier 7b` → embeds → prints stats

