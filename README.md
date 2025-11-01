# LLM Commander

LLM Commander centralizes our local-first orchestration assets so new LLM-driven TUI projects can be scaffolded in minutes. It packages the codex wrapper, context packaging utilities, and the reusable project template that we have been iterating on across repos.

## What's Included
- `scripts/codex_wrap.sh`: smart routing shell wrapper that delegates to local Qwen, Gemini API, or premium Codex based on task complexity.
- `scripts/llm_gateway.js`: Node gateway that streams prompts to Ollama or Gemini with environment flag controls.
- `tools/create_context_zip.py`: context packager that emits `llmccontext*.zip` archives honoring `.gitignore`.
- `template/`: ready-to-copy base tree (contracts, agent docs, codex assets) for spinning up new projects.

## Getting Started
1. Run `chmod +x scripts/*.sh` to ensure the orchestration scripts stay executable.
2. Prepare `.env.local` with any needed overrides (e.g., `GEMINI_API_KEY`, `OLLAMA_PROFILE`).
3. Dry-run the local model pipeline: `./scripts/codex_wrap.sh --local "write hello world in python"`.
4. Package a context snapshot when needed: `python tools/create_context_zip.py` (drops the zip in `~/src`).

## Roadmap Notes
- Phase 1 focuses on solidifying the local orchestration shell and smoke-test workflows.
- Phase 2 will experiment with agent orchestration layers and TUI-first project templates.
- Phase 3 targets RAG/MCP integrations plus a web-based command surface once the foundations are stable.

You, like Tron, fight for the user—LLM Commander keeps the support scripts in one place so each new build starts with the same battle-ready toolkit.
