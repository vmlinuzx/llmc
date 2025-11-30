
# SDD – Phase 1, Change 4: Tests for Safety & Priority

## Scope
Add regression tests covering:
- None/empty input → docs low confidence with reason token.
- Fenced code detection (with/without language tag; multiple blocks).
- Inline backticks are *not* fences.
- Code vs ERP conflicts where fences or structure must win.

## Outcome
The test set guards the Phase 1 safety and priority guarantees against future regressions.
