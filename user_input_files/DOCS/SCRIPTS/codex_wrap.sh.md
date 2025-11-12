# codex_wrap.sh — Smart LLM Router and Prompt Builder

Path
- scripts/codex_wrap.sh

Purpose
- Primary entrypoint for local development. Builds a full prompt (contracts slice, optional RAG plan + context, system notes) and routes the task to one of: local Ollama, API (Gemini/Azure), or Codex, with semantic-cache lookup.

Usage
- `scripts/codex_wrap.sh [options] [prompt|prompt_file]`
- Flags:
  - `-l, --local` force local Ollama
  - `-a, --api` force API fallback
  - `-c, --codex` force Codex CLI
  - `-ca, --codex-azure` force Azure Codex/Responses (if configured)
  - `-m, --minimax` force routing to MiniMax M2 API
  - `--repo PATH` run against a different repo root (affects .rag, logs, contracts)  - `-h, --help` show help

Key environment variables
- Logging: `CODEX_WRAP_ENABLE_LOGGING=1` (default), `CODEX_LOG_FILE=logs/codexlog.txt`, `CODEX_WRAP_FORCE_LOGGING=1` (tee even on TTY)
- Approval passthrough to Codex CLI: `CODEX_APPROVAL|APPROVAL_POLICY` (maps to `-a {untrusted|on-failure|on-request|never}`)
- Context slicing: `CONTRACT_SUMMARY_LINES` (default 60), `AGENTS_SUMMARY_LINES` (default 60), `CONTEXT_HINTS="contract:Constraints,Flows;agents:Testing Protocol"`
- RAG: honors `CODEX_WRAP_DISABLE_RAG`, sees `scripts/rag_plan_helper.sh` output and inserts it before the user prompt
- Semantic cache: `SEMANTIC_CACHE_*` knobs (min score/overlap, provider, enable/disable, probe mode)
- Azure: `AZURE_OPENAI_ENDPOINT|KEY|DEPLOYMENT[_CODEX[_LIST]]|API_VERSION|MAX_TOKENS|TEMPERATURE`
- General: `LLMC_TARGET_REPO` (repo root), `LLMC_EXEC_ROOT` (tooling root), `PYTHON_BIN` for helper CLIs

Behavior highlights
- Pre-arg scan for `--repo` to establish roots before reading files
- Emits deep research hints via tools.deep_research.detector; can gate non-local routes until notes are ingested
- Prompt pipeline: contracts sidecar slice → optional RAG plan block → user content
- Route decision: explicit flags > deep-research gate > LLM router prompt (Gemini via `llm_gateway.sh`)
- Semantic cache lookup before execution; returns cached answer when score ≥ threshold

Side effects
- Appends traces to `logs/codexlog.txt` (unless disabled)
- May write cache files under `~/.cache/codex_wrap/` or `.cache/codex_wrap/`

Exit codes
- 0 on success; non-zero on failures from invoked backends or missing configuration (e.g., Azure forced without env)

Related docs
- scripts/SMART_ROUTING.md, DOCS/preprocessor_flow.md, DOCS/RAG_Freshness_Automation.md

