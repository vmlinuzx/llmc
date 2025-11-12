# claude_wrap.sh — Claude API Wrapper with Context Slices

Path
- scripts/claude_wrap.sh

Purpose
- Build a targeted prompt for Claude by slicing `CONTRACTS.md` and `CLAUDE_AGENTS.md`, optionally including a RAG plan and using a semantic cache to short‑circuit identical prompts.

Usage
- `echo "fix the failing test" | scripts/claude_wrap.sh`
- Reads stdin as the user prompt. Honors `CONTEXT_HINTS` to select specific headings from the source markdown.

- Flags:
  - `-l, --local` force local Ollama
  - `-a, --api` force API fallback
  - `-c, --claude` force Claude Code CLI
  - `-ca, --claude-azure` force Claude Code with Azure OpenAI
  - `-m, --minimax` force routing to MiniMax M2 API
  - `--azure` use Azure OpenAI backend for Claude
  - `--repo PATH` run against a different repo root (affects .rag, logs, contracts)
  - `-h, --help` show help

Key env vars
- Slicing: `CONTEXT_HINTS`, `CONTRACT_SUMMARY_LINES`, `AGENTS_SUMMARY_LINES`
- RAG: `LLMC_RAG_INDEX_PATH` (auto-detected from `.rag/`), disable via `LLM_GATEWAY_DISABLE_RAG=1`
- Semantic cache: `SEMANTIC_CACHE_*` knobs; provider defaults to `GEMINI_MODEL`
- Python helper: `PYTHON_BIN` for `tools.cache.cli` lookups

Outputs & side effects
- Writes cached slices to `~/.cache/codex_wrap/` or `.cache/codex_wrap/`
- Emits responses to stdout; logs/diagnostics to stderr

Related
- scripts/SMART_ROUTING.md, DOCS/preprocessor_flow.md

