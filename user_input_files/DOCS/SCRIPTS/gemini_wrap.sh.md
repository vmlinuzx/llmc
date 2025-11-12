# gemini_wrap.sh — Gemini API Wrapper with Context Slices

Path
- scripts/gemini_wrap.sh

Purpose
- Mirror of `claude_wrap.sh` tuned for Gemini contracts files (`GEMINI_CONTRACTS.md`, `GEMINI_AGENTS.md`). Slices context, optionally injects RAG plan, and consults semantic cache before calling Gemini.

Usage
- `echo "summarize recent changes" | scripts/gemini_wrap.sh`

Key env vars
- Slicing: `CONTEXT_HINTS`, `CONTRACT_SUMMARY_LINES`, `AGENTS_SUMMARY_LINES`
- RAG index detection via `LLMC_RAG_INDEX_PATH`; disable with `LLM_GATEWAY_DISABLE_RAG=1`
- Cache: `SEMANTIC_CACHE_*`; provider defaults to `GEMINI_MODEL`

Notes
- This wrapper focuses on prompt assembly; actual transport is handled by the gateway/SDK invoked within the script.

