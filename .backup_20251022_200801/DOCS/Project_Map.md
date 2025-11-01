# Project Map (Template)

## Top-level
- app/ or src/ — application code
- components/ — UI building blocks
- services/ — API and integration clients
- scripts/ — automation, orchestration, dev utilities
- DOCS/ — documentation and operating procedures
- tests/ — automated tests

## Scripts
- scripts/codex_wrap.sh — routing wrapper (local/API)
- scripts/llm_gateway.* — local-first LLM gateway
- scripts/sync_to_drive.sh — background docs/context sync

## Conventions
- Keep functions small and pure where possible
- One responsibility per file where feasible
- Prefer explicit exports/imports
- Keep module boundaries clear (avoid deep cross-deps)
