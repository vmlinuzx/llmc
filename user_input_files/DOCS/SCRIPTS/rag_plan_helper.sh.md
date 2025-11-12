# rag_plan_helper.sh — Emit RAG Planner Snippet

Path
- scripts/rag_plan_helper.sh

Purpose
- Read a user query from stdin and print a compact “RAG Retrieval Plan” plus indexed context if a `.rag/` database is present.

Usage
- `echo "Where do we validate JWTs?" | scripts/rag_plan_helper.sh [--repo PATH]`

Env
- Disable via `CODEX_WRAP_DISABLE_RAG=1` or `LLM_GATEWAY_DISABLE_RAG=1`
- Index path override: `LLMC_RAG_INDEX_PATH`

Notes
- Wrapper around `scripts/rag_plan_snippet.py`; returns empty output when no index is found or the query is blank.

