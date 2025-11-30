
# SDD – Phase 1, Change 2: Reorder Heuristic Priority

## Summary
Ensure strong and weak code signals are evaluated **before** ERP patterns so code is never misrouted to ERP merely due to overlapping keywords.

## Design
- Add an early priority block in `classify_query`:
  1. Fenced code → return `"code"`, high confidence.
  2. Code structure regex → return `"code"`, high confidence.
  3. Code keywords → return `"code"`, moderate confidence.
  4. (Subsequent logic may evaluate ERP; unreachable for the above hits.)

- Minimal fenced-code detector that requires:
  - A fence opener at line start (```lang?).
  - A closing fence later in the text.

## Acceptance Criteria
- Queries containing fenced blocks route to code even with ERP keywords present.
- Code structure (e.g., `def`, `class`, imports, assignments) routes to code before ERP.
- Single code keyword (e.g., `return`) routes to code with lower confidence than structure/fence.

## Out of Scope
- Overhaul of ERP regex patterns.
- Metrics/telemetry (Phase 4).
