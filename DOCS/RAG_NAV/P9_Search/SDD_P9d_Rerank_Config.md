# SDD — P9d: Rerank Tuning & Config

**Goal:** Configurable reranker weights via `.llmc/rag_nav.ini` and environment variables. Includes a tiny A/B canary evaluator.

## Config
- File: `.llmc/rag_nav.ini`
```
[rerank]
bm25 = 0.60
uni  = 0.20
bi   = 0.15
path = 0.03
lit  = 0.02
```
- Environment overrides (precedence over INI):
`RAG_RERANK_W_BM25, RAG_RERANK_W_UNI, RAG_RERANK_W_BI, RAG_RERANK_W_PATH, RAG_RERANK_W_LIT`
- Weights normalized to sum to 1.0; invalid values ignored.

## Interfaces
- `tools.rag.config.load_rerank_weights(repo_root) -> dict`
- `tools.rag.rerank.rerank_hits(query, hits, top_k=20, weights=None)`
