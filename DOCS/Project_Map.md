# Project Map

## Top-Level Overview
- `apps/` — user-facing applications; currently houses the Next.js App Router MVP (`template-builder/`) and a lightweight Express archive service (`web/`).
- `scripts/` — automation entrypoints (e.g. `codex_wrap.sh`, `llm_gateway.js`, `rag_refresh_cron.sh`) that orchestrate local/remote LLM workflows and RAG maintenance.
- `tools/` — reusable Node/Python packages backing automation and retrieval (notably `tools/rag/` and `tools/deep_research/`).
- `config/` — declarative configuration for agent routing, RAG, and orchestration policies.
- `DOCS/` — operational manuals, roadmaps, and working notes (includes rate-limit bypass playbooks in `AGENTS.md` and the roadmap in `DOCS/Roadmap.md`).
- `llmc_exec/` — multi-repo CLI helpers and shared scaffolding invoked by orchestrators.
- `mcp/` — Model Context Protocol adapters and resources for desktop/FS agents.
- `logs/` — run logs emitted by wrappers; `.gitignore` retains structure but drops contents.
- `research/` — in-progress investigations and import queues that feed back into `DOCS/RESEARCH/`.
- `PATCHES/`, `examples/`, `template/`, `test_azure_openai.sh` — supporting artifacts for experiments, archived bundles, and targeted validation.

## Applications (`apps/`)
- `template-builder/` — Next.js 14 App Router UI for assembling Codex-ready bundles; includes API routes (`app/api/**`), bundle logic (`lib/generateBundle.ts`), and Jest/Playwright tests.
- `web/` — Express-based ZIP generator that mirrors historical template production; reads from `/template` and exposes `/generate`.

## Automation & Orchestration
- `scripts/codex_wrap.sh` — primary launcher that routes tasks to local Ollama or future API backends.
- `scripts/llm_gateway.js` — Node CLI translating profile flags into concrete model invocations.
- `scripts/rag_*` & `tools/rag/` — ingestion and refresh utilities for the semantic index.
- `scripts/run_mcpo_bridge.sh`, `scripts/integration_gate.sh` — coordination helpers for MCP bridges and CI-style smoke flows.

## Documentation & Governance
- `DOCS/Roadmap.md` — live priorities (e.g. Template Builder MVP, RAG planner integration).
- `AGENTS.md`, `CLAUDE_AGENTS.md`, `GEMINI_AGENTS.md` — operating contracts per assistant.
- `CONTRACTS.md` — umbrella guardrails referenced by bundle generation.
- `DOCS/RESEARCH/` (ignored in git) — large design studies and supporting PDFs kept local.

## Supporting Assets
- `llmc_exec/bin/*` — shim executables shared by orchestrators.
- `logs/` & `.llmc/` — runtime state (locks, ledgers) required for long-lived sessions.
- `template/` — base scaffolds zipped by legacy services; kept for compatibility.

### Conventions
- Prefer small, composable modules with explicit exports.
- Keep automation scripts idempotent and scoped to the repo root.
- Treat docs as the source of truth for agent contracts; update them alongside behaviour changes.
