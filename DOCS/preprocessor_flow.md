# Preprocessor Pipeline Overview

Summarizes the local preprocessing pipeline before heavy LLM calls.

## Index
- `python -m tools.rag.cli index`
- Refresh specific paths: `python -m tools.rag.cli sync --since <commit>` or provide path list.

## Enrich
- Batch runner: `python scripts/qwen_enrich_batch.py --cooldown 600`
  - `--cooldown` waits N seconds after last file touch before re-enriching.
  - Other knobs: `--sleep`, `--retries`, `--retry-wait`, `--log`.
- CLI alternative: `python -m tools.rag.cli enrich --execute --cooldown 600`
- Metrics: `logs/enrichment_metrics.jsonl` (watch via `./scripts/enrichmentmetricslog.sh` or tail with `./scripts/enrichmenttail.sh`).

## Embeddings
- `python -m tools.rag.cli embed --execute`
- Smoke test: `./scripts/embed_smoke_test.sh`.

## Planner
- `python -m tools.rag.cli plan "Where do we validate JWTs?"`
- Logs: `logs/planner_metrics.jsonl` (`./scripts/plannermetricslog.sh`).

## Gateway Routing
- Local default (`./scripts/codex_wrap.sh --local`).
- Azure: set `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`, run with `--api` or set `LLM_GATEWAY_DISABLE_LOCAL=1`.
- Logs: `logs/codexlog.txt` (`./scripts/codexlogtail.sh`).

## Helper Scripts
- `scripts/enrichmentmetricslog.sh` – watch enrichment summary.
- `scripts/plannermetricslog.sh` – watch planner summary.
- `scripts/enrichmenttail.sh` – tail enrichment JSONL.
- `scripts/codexlogtail.sh` – tail gateway log.

## Environment Flags
- `LLM_DISABLED`, `NEXT_PUBLIC_LLM_DISABLED`, `WEATHER_DISABLED` – hard-disable LLM usage.
- `LLM_GATEWAY_DISABLE_LOCAL` – force API usage.
- `LLM_GATEWAY_DISABLE_API` – forbid API fallback.

Update this doc as the pipeline evolves (doc generation, testing hooks, etc.).

## Sample Run: Qwen 2.5 Local vs. GPT-5 Nano (Azure)

```
Qwen 2.5 (local via Ollama)
Stored enrichment 1: app/search/page.tsx:21-348 (164.79s)
Stored enrichment 2: app/sites/page.tsx:18-24 (320.33s)
Stored enrichment 3: app/sites/page.tsx:35-346 (348.81s)
Stored enrichment 4: app/sites/[id]/SiteIndicators.tsx:34-146 (322.22s)
Stored enrichment 5: app/sites/[id]/SiteIndicators.tsx:148-164 (353.37s)
Stored enrichment 6: app/sites/[id]/SiteIndicators.tsx:166-169 (320.61s)
Stored enrichment 7: app/sites/[id]/SiteIndicators.tsx:171-185 (331.69s)
Stored enrichment 8: app/sites/[id]/not-found.tsx:3-17 (338.43s)
Stored enrichment 9: app/sites/[id]/page.tsx:13-17 (354.31s)

GPT-5 Nano (Azure)
[indexenrich-azure] Updating enrichment metadata via Azure
Stored enrichment 1: docs/preprocessor_flow.md:1-4 (12.39s)
Stored enrichment 2: docs/preprocessor_flow.md:5-9 (24.03s)
Stored enrichment 3: docs/preprocessor_flow.md:10-14 (24.88s)
Stored enrichment 4: docs/preprocessor_flow.md:15-19 (26.12s)
Stored enrichment 5: docs/preprocessor_flow.md:20-24 (33.96s)
Stored enrichment 6: docs/preprocessor_flow.md:25-29 (34.39s)
Stored enrichment 7: docs/preprocessor_flow.md:30-35 (16.00s)
Stored enrichment 8: DOCS/preprocessor_flow.md:1-4 (19.06s)
Stored enrichment 9: DOCS/preprocessor_flow.md:5-8 (19.94s)
Stored enrichment 10: DOCS/preprocessor_flow.md:9-15 (22.07s)
Stored enrichment 11: DOCS/preprocessor_flow.md:16-19 (20.96s)
Stored enrichment 12: DOCS/preprocessor_flow.md:20-23 (17.79s)
Stored enrichment 13: DOCS/preprocessor_flow.md:24-28 (14.41s)
Stored enrichment 14: DOCS/preprocessor_flow.md:29-34 (19.36s)
Stored enrichment 15: DOCS/preprocessor_flow.md:35-40 (14.78s)
```
