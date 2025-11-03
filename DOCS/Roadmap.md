# Roadmap (Template)

## Phases
- P0 – Immediate: critical bugs, auth, deploy blockers
- P1 – Core: main feature set, happy-path flows
- P2 – Quality: performance, DX polish, observability, docs
- P3 – Nice-to-have: experiments, stretch goals

## Current Priorities
- [ ] Define MVP scope (1–2 weeks of work)
  - Deliver a generic web interface where users select orchestration + tooling preferences.
  - Generate a zipped starter template that mirrors the Codex commander repo layout.
  - Ensure selections drive config files so an LLM can immediately assist after download.
- [ ] Lock technical choices (framework, DB, auth, hosting)
  - Stay 100% open source with a cost-free "poor folks" stack.
  - Base project on Next.js App Router with `app/` + API routes.
  - Use Postgres via Prisma (docker-compose for local dev, pg in prod).
  - Wire up NextAuth for auth and basic upload endpoints.
  - Ship container-friendly Dockerfile + compose for local + server deploys.
- [ ] Ship first vertical slice end-to-end

## Backlog
- [ ] Performance profiling baseline
- [ ] Error tracking and alerts
- [ ] Accessibility pass (keyboard, color contrast)

Notes
- Keep items small (1–3 days each)
- Update weekly; archive completed under a “Done” section
