# LLM Commander

LLM Commander is the home for our local-first orchestration stack. It combines the Template Builder MVP, automation scripts, and retrieval tooling that power Codex, Claude, and Gemini workflows with reproducible guardrails.

## Core Components
- `apps/template-builder/` — Next.js 14 App Router UI for composing Codex-ready bundles. Includes API routes (`app/api`), bundle logic (`lib/`), and Jest/Playwright tests.
- `apps/web/` — Legacy Express ZIP service that reads from `template/` to produce archives; kept for compatibility.
- `scripts/` — Shell and Node entrypoints such as `codex_wrap.sh`, `llm_gateway.js`, and `rag_refresh_cron.sh` that route tasks to local Ollama or remote APIs.
- `tools/` — Shared Python utilities (`tools/rag/`, `tools/deep_research/`, `tools/create_context_zip.py`) for indexing, enrichment, and research automation.
- `config/` & `llmc_exec/` — Configuration and shared CLI helpers consumed by orchestrators and MCP connectors.
- `DOCS/` — Operating manuals, roadmap, and contract files (see `DOCS/Roadmap.md`, `AGENTS.md`, `CONTRACTS.md`, and `DOCS/Template_Builder.md`).

## Getting Started
- Ensure shell scripts stay executable: `chmod +x scripts/*.sh`.
- Create `.env.local` at the repo root with any overrides (`GEMINI_API_KEY`, `OLLAMA_PROFILE`, etc.). Defaults fall back to Qwen 2.5 local models.
- Dry-run the orchestrator: `./scripts/codex_wrap.sh --local "generate hello world in python"`.
- Build context archives when needed: `python tools/create_context_zip.py` (writes to `template/` by default).

## Template Builder MVP
- Development: `cd apps/template-builder && npm run dev` (Next.js dev server on port 3000).
- Build: `npm run build && npm run start`.
- Tests: `npm run test` (Jest unit/integration) and `npm run test:e2e` (Playwright, requires dev server).
- API routes (`/api/options`, `/api/generate`) pull live registry data from repo docs and emit Codex-ready bundles including contracts, agent manifests, and environment scaffolds.

## CLI Orchestration Workflow
- `scripts/codex_wrap.sh` routes prompts to a local Qwen 14B profile by default, with flags for remote APIs (`--api`, `--minimax`) when environment variables are present.
- `scripts/llm_gateway.js` resolves model profiles (`code`, `fast`, `uncensored`) defined in-place and respects `OLLAMA_PROFILE` / `OLLAMA_MODEL`.
- Logs land in `logs/` (git-ignored contents) and `.llmc/` maintains locks/worktrees for concurrent sessions.

## Retrieval & Research Utilities
- `scripts/rag_refresh.sh`, `scripts/rag_refresh_watch.sh`, `scripts/rag_refresh_cron.sh`, and `tools/rag/` keep the semantic index fresh (default embeddings: MiniLM with migration in progress per `DOCS/Roadmap.md`).
- `tools/deep_research/` and `scripts/deep_research_ingest.sh` coordinate long-form investigations captured under `research/`.

## Documentation Hub
- `DOCS/Project_Map.md` — Current repo topology.
- `DOCS/Roadmap.md` — Active priorities (Template Builder MVP, RAG planner integration).
- `AGENTS.md` / `CLAUDE_AGENTS.md` — Execution contracts for the orchestration agents.
- `DOCS/Template_Builder.md` — UX notes and future enhancements for the Next.js interface.

You, like Tron, fight for the user—LLM Commander keeps the orchestration toolkit synchronized so every new build starts from the same battle-ready foundation.
