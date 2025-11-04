# Roadmap (Template)

## Phases
- P0 – Immediate: critical bugs, auth, deploy blockers
- P1 – Core: main feature set, happy-path flows
- P2 – Quality: performance, DX polish, observability, docs
- P3 – Nice-to-have: experiments, stretch goals

## Current Priorities
- [ ] Pipe RAG planner output into `codex_wrap.sh` / `llm_gateway.js` so Codex, Claude, and Gemini consume indexed spans automatically before answering.
- [ ] Automate RAG freshness (hourly or on-change) via `scripts/rag_sync.sh` + tmux/cron so `.rag/index.db` stays current without manual kicks.
- [ ] Ship the template builder MVP (Next.js App Router UI) that builds Codex-ready zips based on orchestration choices.
- [ ] Deliver the first vertical slice end-to-end using the new template + RAG-aware workflow.

## Recently Completed
- [x] Define MVP scope (generic web UI, templated configs, Codex-ready zip).
- [x] Lock technical choices (Next.js App Router, Prisma/Postgres, NextAuth, Docker/Compose, fully OSS stack).

## Backlog
- [ ] Performance profiling baseline
- [ ] Error tracking and alerts
- [ ] Accessibility pass (keyboard, color contrast)

Notes
- Keep items small (1–3 days each)
- Update weekly; archive completed under a “Done” section
