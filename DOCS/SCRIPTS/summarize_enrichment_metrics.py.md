# summarize_enrichment_metrics.py — Roll Up Enrichment Metrics

Path
- scripts/summarize_enrichment_metrics.py

Purpose
- Read `logs/enrichment_metrics.jsonl` and print counts plus latency/token summaries.

Usage
- `python3 scripts/summarize_enrichment_metrics.py [--log logs/enrichment_metrics.jsonl]`

Output
- Prints entries analyzed, latency min/max/avg, token heuristics and saved totals.

