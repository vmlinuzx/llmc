# Template + RAG Vertical Slice Plan

## Goal

Deliver the first end-to-end slice that proves a freshly generated bundle can:

1. Bootstrap the Next.js template workspace.
2. Refresh RAG context and surface it through `codex_wrap.sh`.
3. Walk the “author spec → compress if needed → codex execution → smoke test” loop without manual patching.

## Current baseline

- `apps/template-builder` renders the UI and assembles bundles by copying `template/` and customising `.codex/tools.json` plus `.codex/config.toml` before adding contracts, agents, and env presets (`apps/template-builder/lib/generateBundle.ts:51-481`).
- The template blueprint only ships orchestration config (`template/.codex/*`, `template/.llm/*`, `.vscode/`) with no application code or RAG helpers (`template/.codex/config.toml`, `template/.llm/presets/claude_system.txt`).
- Agent manifests emitted today point to `agents/<tool>.mjs`, but no entry point modules exist yet (`apps/template-builder/lib/generateBundle.ts:174-181`).

## Gaps to close

1. **Application skeleton** — create a minimal Next.js App Router + Prisma/Postgres + NextAuth stack inside `template/`, including Docker/Compose and seed data, so bundles are runnable out of the box.
2. **Agent runtime assets** — add executable MCP agents (or adjust manifests) and ensure tooling like Desktop Commander + fs-project are available alongside their configs.
3. **RAG automation** — include scripts/env for indexing (`scripts/rag_refresh.sh`, `tools/rag/cli.py`) and document how bundles trigger refreshes or use the shared `llmc_exec` toolkit.
4. **Verification & docs** — script a smoke test that unpacks a bundle, runs the RAG + codex loop, and document the workflow for users.

## Proposed sequence

1. Populate `template/` with the application skeleton and regenerate bundle tests to assert the new files appear.
2. Ship agent modules or swap manifests to existing executables, updating `template/.codex/tools.json` defaults and builder output.
3. Wire RAG helpers into the template (venv bootstrap, cron wrapper, docs) and expose toggles in the builder if needed.
4. Add an end-to-end task (CI script or manual playbook) that exercises the flow and codifies acceptance signals.

## Definition of done

- Generating a bundle, unpacking it into a clean directory, and running the documented commands yields a working Next.js app with codex + RAG context available.
- The smoke script passes locally and is referenced from `DOCS/Roadmap.md`.
- Follow-up backlog items (perf profiling, compressor guardrails) are logged with clear owners.
