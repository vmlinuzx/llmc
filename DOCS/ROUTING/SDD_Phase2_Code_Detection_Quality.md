
# SDD – Phase 2: Code Detection Quality

## Summary
Introduce small, composable heuristics that improve code detection while keeping `classify_query` readable.

## Changes
- Replace single `CODE_STRUCT_REGEX` with `CODE_STRUCT_REGEXES` list:
  - defs/classes, imports, assignments, loops, lambdas, basic calls.
- Expand `CODE_KEYWORDS` and treat 1+ keyword as a weak code signal (still below structure and fences).
- Keep priority guarantees from Phase 1 (code > ERP > docs).

## Tests
See `tests/routing/test_query_type_phase2_code_quality.py` for regression coverage.
