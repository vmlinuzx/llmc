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

## Batch Enrichment Tips
- Use `python scripts/qwen_enrich_batch.py --cooldown 600` (or the `rag enrich --cooldown 600` CLI) to skip spans touched in the last 10 minutes before re-enriching.
- Cooldowns prevent thrashing while you iterate on a file; once the window expires, the span re-enters the queue automatically.

- To hit Azure OpenAI instead of Qwen, set `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` in `.env.local` and run with `--api` (or set `LLM_GATEWAY_DISABLE_LOCAL=1`); the gateway will prefer Azure when those vars are present.

## Roadmap Notes
- Phase 1 focuses on solidifying the local orchestration shell and smoke-test workflows.
- Phase 2 will experiment with agent orchestration layers and TUI-first project templates.
- Phase 3 targets RAG/MCP integrations plus a web-based command surface once the foundations are stable.
- Ongoing: expand testing to additional real-world repos (e.g., Supabase-style web apps, data-heavy services) to benchmark enrichment, embeddings, and the planner pipeline end-to-end.
- Upcoming: build a zip-ready "LLMC Toolkit" template (enrichment + planner + embedding wiring, safety rails, verification) for drop-in use across Claude/Gemini/Codex projects.
- Local query planner: use lightweight model to turn asks into {symbols, files, functions, intents} before retrieval (cuts shotgun pulls by 50–90%).
- Symbol map over raw code via ctags/tree-sitter to answer many "where/how" questions from signatures without loading bodies.
- Evidence packs only: fetch enrichment-cited line ranges (+/- 5 lines) instead of whole files.
- Local re-ranker (cosine/BM25 hybrid) to prune to top 3–5 spans before any paid LLM call.
- Delta-aware updates so only changed spans re-enrich; answer "what changed" from diffs.
- Memoize QA by span hash so repeat queries short-circuit with freshness checks.
- Prefer docstrings/enrichment cards over raw code; fall back to source only when cards flag pitfalls/side-effects.
- Local doc compressor: pre-bullet README/ADR/issues with IDs and retrieve bullets first.
- Tool-first answers: use deterministic helpers (AST/query eval) for config/JSON/SQL/regex before LLM.
- Strict prompt hygiene: single short system prompt and minimal JIT few-shot; trim boilerplate in every call.

- Orchestrator self-improvement tools: manual enrichment editor, span-hash-driven unit test generator, and AST-based safe refactor helpers.
- Observability & evaluation: interactive RAG dashboard plus an evaluation harness running golden queries versus expected spans.
- Onboarding upgrades: interactive `llmc init` wizard and `llmc doctor` dependency checker to streamline adoption.

You, like Tron, fight for the user—LLM Commander keeps the support scripts in one place so each new build starts with the same battle-ready toolkit.
