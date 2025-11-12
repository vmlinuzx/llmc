# qwen_enrich_batch.py — Batch Enrichment Orchestrator

Path
- scripts/qwen_enrich_batch.py

Purpose
- Drive enrichment of indexed spans using local Ollama (7B/14B), gateway/API, and router heuristics. Validates outputs and records metrics.

Inputs/outputs
- Reads `.rag/index*.db` via `tools.rag.database` and writes enrichments + metrics to `logs/enrichment_metrics.jsonl`.

Key options (selected)
- `--repo PATH` repo root containing `.rag/`
- `--backend {ollama,gateway}` which transport to use
- `--router {on,off}` enable/disable tier router
- `--start-tier {auto,7b,14b,nano}` initial tier (router refined)
- `--batch-size N` number of spans per pass; `--max-spans N` overall cap (0 = unlimited)
- `--cooldown SECONDS` delay between spans to control GPU/CPU load

Important env
- `ENRICH_OLLAMA_HOSTS` (comma list of label=url) or `OLLAMA_URL`; also consults `ATHENA_OLLAMA_URL`
- GPU/VRAM watchdog thresholds and utilization logging; warnings at ~6.8 GiB

Failure handling
- Detects truncation/parse/validation errors and escalates tier (7B → 14B → nano) based on `router.py` policies

Related modules
- `scripts/router.py`, `tools.rag.workers` (plan/validate), `tools.rag.config`

