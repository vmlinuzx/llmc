# record_enrichment_metrics.py — Validate + Store Enrichment + Log Metrics

Path
- scripts/record_enrichment_metrics.py

Purpose
- Validate an enrichment payload against a planned span, store it in the RAG DB, and append a metrics record to JSONL.

Usage (abridged)
- `python3 scripts/record_enrichment_metrics.py --plan plan.json --payload out.json --latency 12.3 [--log logs/enrichment_metrics.jsonl] [--model qwen2.5:14b] [--schema-version enrichment.v1]`

Effects
- Writes to `.rag/index.db` and appends a line to `logs/enrichment_metrics.jsonl` with latency and token estimates.

