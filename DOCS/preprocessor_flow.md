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
