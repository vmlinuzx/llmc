# rag_plan_snippet.py — Planner + Indexed Context Emitter

Path
- scripts/rag_plan_snippet.py

Purpose
- Given a natural‑language query, generate a ranked plan of spans and emit a concise bundle: plan header, rationale, and clipped code/doc snippets from the index.

Usage
- `python3 scripts/rag_plan_snippet.py --repo <path> --limit 5 --min-score 0.4 --min-confidence 0.6 <query...>`
- Reads stdin when no args are provided. Exits quietly if no index exists.

Options
- `--repo PATH` repository root
- `--limit N` max spans to include (default 5)
- `--min-score F` minimum span score to keep (default 0.4)
- `--min-confidence F` overall confidence threshold (default 0.6)
- `--no-log` skip planner metrics
- `--total-char-limit N` aggregate context cap (env `RAG_PLAN_CONTEXT_CHAR_LIMIT` default 16000)
- `--span-char-limit N` per-span cap (env `RAG_PLAN_SPAN_CHAR_LIMIT` default 3200)

Notes
- Detects `.rag/index_v2.db` or falls back to `.rag/index.db`.
- Looks up enrichments to include metadata (summary, inputs/outputs, side effects, pitfalls, usage snippet) when available.

