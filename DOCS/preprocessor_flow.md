# Preprocessor Pipeline Overview

This cheat sheet mirrors the preprocessing pipeline that feeds the Codex-style orchestrator. Keep it handy when iterating on the RAG stack.

## Stage 1 – Index
- `python -m tools.rag.cli index` to rebuild from scratch.
- Incremental: `python -m tools.rag.cli sync --since <commit>` or pass explicit paths.
- Output: `.rag/index_v2.db` (files, spans, hashes) — fallback to `.rag/index.db` when the v2 index is absent.

## Stage 2 – Enrich
- Batch: `python scripts/qwen_enrich_batch.py --cooldown 600`.
  - Retries escalate from Qwen 7B → `--fallback-model` (default `qwen2.5:14b-instruct-q4_K_M`) → gateway (GPT-5 nano) on parse/validation failures.
  - Other knobs: `--sleep`, `--retries`, `--retry-wait`, `--log`.
  - Router heuristics disabled as of November 4, 2025; every span starts on Qwen 7B and only promotes to 14B or nano when validation fails.
- Manual: `python -m tools.rag.cli enrich --execute --cooldown 600`.
- Metrics land in `logs/enrichment_metrics.jsonl`; tail with `./scripts/enrichmentmetricslog.sh` or `./scripts/enrichmenttail.sh`.

## Stage 3 – Embed
- `python -m tools.rag.cli embed --execute --limit 50`.
- Default embedding model: `intfloat/e5-base-v2` with `passage:` / `query:` prefixing and L2-normalized vectors (tune via `EMBEDDINGS_MODEL_NAME`, `EMBEDDINGS_PASSAGE_PREFIX`, `EMBEDDINGS_QUERY_PREFIX`).
- GPU guardrails: the embed step waits for at least ~1.5 GB of free VRAM and automatically falls back to CPU if the card stays busy (tweak via `EMBEDDINGS_WAIT_FOR_GPU`, `EMBEDDINGS_GPU_MIN_FREE_MB`, `EMBEDDINGS_DEVICE`).

## Stage 4 – Semantic Cache (answer reuse)
- Lookup happens automatically in `codex_wrap.sh`, `claude_wrap.sh`, and `gemini_wrap.sh` before any LLM call. Misses are stored after a successful completion.
- Inspect / manage from the CLI:
  - `python -m tools.cache.cli stats`
  - `python -m tools.cache.cli list --route codex --limit 5`
  - `python -m tools.cache.cli lookup --route codex --prompt-file prompt.txt`
- Configuration knobs:
  - `SEMANTIC_CACHE_DISABLED=1` to turn it off.
  - `SEMANTIC_CACHE_MIN_SCORE=0.99` (default 0.985) adjusts the cosine hit threshold.
  - `SEMANTIC_CACHE_MIN_OVERLAP=0.7` (default 0.6) sets the minimum lexical overlap of user prompts before a semantic hit is trusted.
  - `SEMANTIC_CACHE_REQUIRE_OVERLAP=0` disables keyword gating (default enforces overlap).
  - `SEMANTIC_CACHE_DB=/path/to/cache.db` chooses the SQLite store (default `.cache/semantic_cache.db`).
  - `SEMANTIC_CACHE_ENABLE=0` (alternate disable flag).
  - `SEMANTIC_CACHE_PROBE=1` forces cache lookups to log hit/miss decisions but still execute the LLM (useful for testing).
- Entries are keyed by the fully constructed prompt (including RAG context) with embeddings generated via the same E5 backend for similarity checks.
- Smoke test: `./scripts/embed_smoke_test.sh`.
- Confirm status: `python -m tools.rag.cli stats` (check Embeddings column).
- Deterministic hash embeddings keep this stage offline-friendly.

## Stage 4 – Planner
- `python -m tools.rag.cli plan "Where do we validate JWTs?"`.
- Logs append to `logs/planner_metrics.jsonl`; watch with `./scripts/plannermetricslog.sh`.
- Planner ranks enrichment summaries before any heavy LLM call.

## Stage 5 – Gateway Routing
- Default local run: `./scripts/codex_wrap.sh --local "task"`.
- Azure fallback: set `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, `AZURE_OPENAI_DEPLOYMENT`, optionally `AZURE_OPENAI_API_VERSION`, then run with `--api` or `LLM_GATEWAY_DISABLE_LOCAL=1`.
- Gemini fallback stays active when Azure variables are absent and `GEMINI_API_KEY` is set.
- Logs: `logs/codexlog.txt` (tail with `./scripts/codexlogtail.sh`).

## Helper Scripts & Flags
- `./scripts/enrichmentmetricslog.sh` – summarize enrichment runs.
- `./scripts/enrichmenttail.sh` – tail raw enrichment JSONL.
- `./scripts/plannermetricslog.sh` – follow planner stats.
- `LLM_DISABLED`, `NEXT_PUBLIC_LLM_DISABLED`, `WEATHER_DISABLED` hard-stop LLM usage.
- `LLM_GATEWAY_DISABLE_LOCAL` forces API usage; `LLM_GATEWAY_DISABLE_API` forbids API fallback.

Keep this doc updated as the pipeline evolves (doc generation, evaluation harnesses, new backends, etc.).

## Automation
- `./scripts/rag_refresh.sh` — one-shot sync/enrich/embed for tracked changes.
- `./scripts/start_rag_refresh_loop.sh` — run in tmux (`./scripts/run_in_tmux.sh -s dc-rag-refresh -- ./scripts/start_rag_refresh_loop.sh`) to refresh hourly (override via `RAG_REFRESH_INTERVAL`).

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
Stored enrichment 1: DOCS/preprocessor_flow.md:1-4 (12.39s)
Stored enrichment 2: DOCS/preprocessor_flow.md:5-9 (24.03s)
Stored enrichment 3: DOCS/preprocessor_flow.md:10-14 (24.88s)
Stored enrichment 4: DOCS/preprocessor_flow.md:15-19 (26.12s)
Stored enrichment 5: DOCS/preprocessor_flow.md:20-24 (33.96s)
Stored enrichment 6: DOCS/preprocessor_flow.md:25-29 (34.39s)
Stored enrichment 7: DOCS/preprocessor_flow.md:30-35 (16.00s)
Stored enrichment 8: DOCS/preprocessor_flow.md:1-4 (19.06s)
Stored enrichment 9: DOCS/preprocessor_flow.md:5-8 (19.94s)
Stored enrichment 10: DOCS/preprocessor_flow.md:9-15 (22.07s)
Stored enrichment 11: DOCS/preprocessor_flow.md:16-19 (20.96s)
Stored enrichment 12: DOCS/preprocessor_flow.md:20-23 (17.79s)
Stored enrichment 13: DOCS/preprocessor_flow.md:24-28 (14.41s)
Stored enrichment 14: DOCS/preprocessor_flow.md:29-34 (19.36s)
Stored enrichment 15: DOCS/preprocessor_flow.md:35-40 (14.78s)
```
