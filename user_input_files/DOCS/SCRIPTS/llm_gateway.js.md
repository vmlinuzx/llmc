# llm_gateway.js — Local‑First LLM Gateway (API Fallbacks)

Path
- scripts/llm_gateway.js (invoked by scripts/llm_gateway.sh)

Purpose
- Try local Ollama first for completions, then fall back to API (Azure Responses/Chat, Anthropic Claude, or Gemini) based on availability/flags. Optionally prepends contracts sidecar and a RAG retrieval plan.

Usage
- Pipe: `echo "prompt" | ./scripts/llm_gateway.sh`
- Arg: `./scripts/llm_gateway.sh "prompt"`
- Force: `--local` | `--api` | `--claude` | `--azure-codex` | `--azure-model <deployment>`
- Repo override: `--repo <path>` (loads `.env.local` from that repo and locates `.rag/`)

Important env vars
- Local model: `OLLAMA_URL` (default http://localhost:11434), `OLLAMA_MODEL`, `OLLAMA_PROFILE` (`code|fast|uncensored`)
- API keys/targets: `GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-2.5-flash`); `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`; `AZURE_OPENAI_ENDPOINT|KEY|DEPLOYMENT[_CODEX|_CODEX_LIST]|API_VERSION`
- Routing toggles: `LLM_GATEWAY_DISABLE_LOCAL`, `LLM_GATEWAY_DISABLE_API`
- Hard disable: if any of `LLM_DISABLED|NEXT_PUBLIC_LLM_DISABLED|WEATHER_DISABLED` are set truthy, or if none of these flags exist at all, the gateway exits early without calling an LLM (Phase 2 behavior)
- Contracts: `CONTRACTS_SIDECAR` (default `contracts.min.json`), `CONTRACTS_VENDOR` (`codex|claude|gemini`), `CONTRACTS_SLICES` (e.g., `roles,tools`), `CONTRACTS_USE_FULL=1` to bypass sidecar

RAG plan injection
- Reads `RAG_USER_PROMPT` (else the user prompt) and calls `scripts/rag_plan_helper.sh` to prepend a compact “RAG Retrieval Plan” + indexed context, bounded by `RAG_PLAN_CONTEXT_CHAR_LIMIT` and `RAG_PLAN_SPAN_CHAR_LIMIT`.

Backend order
1) Azure Responses (when `--azure-codex` or configured)  
2) Claude (when forced or Anthropic configured)  
3) Azure Chat Completions (when configured)  
4) Gemini (fallback)

Outputs
- Prints model text to stdout. Diagnostic routing lines are printed to stderr (e.g., `routing=Local (...)`, `✅ Local model succeeded`).

Exit codes
- 0 on success; non-zero on configuration errors or transport failures.

Related
- scripts/LLM_GATEWAY_README.md, DOCS/SDD_Contracts_Sidecar_v1.md, scripts/rag_plan_helper.sh

