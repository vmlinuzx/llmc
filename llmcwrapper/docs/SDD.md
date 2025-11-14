# SDD: llmcwrapper (Adapter + Dual CLIs + Doctor/Profile/Shadow)
**Date:** 2025-11-12 19:46  
**Status:** Accepted

## Purpose
Stabilize daily workflow by replacing brittle shell wrappers with a small product: shared adapter + two entrypoints + doctor/profile utilities, capability checks, telemetry, and shadow mode.

## Scope
- `llmc-yolo`, `llmc-rag`, `llmc-doctor`, `llmc-profile`
- Adapter with provider routing, invariants, snapshots, telemetry, cost estimates
- Anthropic HTTP driver (messages v1), MiniMax scaffold
- Config: profiles → overlays → one-offs (LLMC_SET/--set/--unset)

## Non-Goals
- Full TUI integration (TUIs call these CLIs)
- Complex pricing correctness (user-configurable; defaults 0)

## Risks/Mitigations
- Provider drift: drivers isolated; capability matrix guards features
- Config sprawl: doctor + snapshots + profile show

## Rollout
1) Install `llmcwrapper` editable; run doctor.
2) Point old shells at `llmc-yolo`/`llmc-rag`; keep for 2 weeks.
3) Wire TUIs and Desktop Commander to call CLIs.
