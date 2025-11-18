# Implementation SDD — P9d Rerank Config

1) Add `tools/rag/config.py` to parse `.llmc/rag_nav.ini` and env vars; return normalized weights.
2) Update `tools.rag.rerank.rerank_hits` to accept optional `weights` (defaults preserved).
3) Wire `tool_rag_search` to call `load_rerank_weights(repo_root)` and pass to `rerank_hits`.
4) Provide `tools/rag/canary_eval.py` and sample `DOCS/RAG_NAV/P9_Search/canary_queries.jsonl`.
