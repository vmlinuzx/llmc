# Preprocessor Pipeline Overview

This cheat sheet mirrors the preprocessing pipeline that feeds the Codex-style orchestrator. Keep it nearby when iterating on the RAG stack.

## Stage 1 – Index
- `python -m tools.rag.cli index` to rebuild from scratch.
- Incremental: `python -m tools.rag.cli sync --since <commit>` or pass explicit paths.
- Output: `.rag/index.db` (files, spans, hashes).

## Stage 2 – Enrich
- Batch: `python scripts/qwen_enrich_batch.py --cooldown 600`.
  - Retries escalate from Qwen 7B → `--fallback-model` (default `qwen2.5:14b-instruct-q4_K_M`) → gateway (GPT-5 nano) on parse/validation failures.
- Manual: `python -m tools.rag.cli enrich --execute --cooldown 600`.
- Metrics land in `logs/enrichment_metrics.jsonl`; tail with `./scripts/enrichmentmetricslog.sh`.

## Stage 3 – Embed
- `python -m tools.rag.cli embed --execute --limit 50`.
- Confirm status: `python -m tools.rag.cli stats` (check Embeddings column).
- Deterministic hash embeddings keep this stage offline-friendly.

## Stage 4 – Planner
- `python -m tools.rag.cli plan "Where do we validate JWTs?"`.
- Logs append to `logs/planner_metrics.jsonl`; watch with `./scripts/plannermetricslog.sh`.
- Planner ranks enrichment summaries before any heavy LLM call.

## Stage 5 – Gateway Routing
- Default local run: `./scripts/codex_wrap.sh --local "task"`.
- Azure fallback: set `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, `AZURE_OPENAI_DEPLOYMENT`, optionally `AZURE_OPENAI_API_VERSION` then run with `--api` or `LLM_GATEWAY_DISABLE_LOCAL=1`.
- Gemini fallback remains active when Azure vars are absent and `GEMINI_API_KEY` is set.

## Helper Scripts & Flags
- `./scripts/enrichmenttail.sh` for live enrichment JSONL.
- `./scripts/codexlogtail.sh` for gateway routing logs (`logs/codexlog.txt`).
- `LLM_DISABLED`, `NEXT_PUBLIC_LLM_DISABLED`, `WEATHER_DISABLED` hard-stop all LLM calls until flipped.

Keep this doc updated as we add doc generation, eval harnesses, or new backends.

## Automation
- `./scripts/rag_refresh.sh` — one-shot sync/enrich/embed for tracked changes.
- `./scripts/start_rag_refresh_loop.sh` — run in tmux (`./scripts/run_in_tmux.sh -s dc-rag-refresh -- ./scripts/start_rag_refresh_loop.sh`) to refresh every hour (override via `RAG_REFRESH_INTERVAL`).

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
