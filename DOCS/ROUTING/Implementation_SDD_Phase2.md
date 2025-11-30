
# Implementation SDD – Phase 2 (Code Detection Quality)

## Touched Files
- `llmc/routing/query_type.py`
- `tests/routing/test_query_type_phase2_code_quality.py`
- `DOCS/ROUTING/SDD_Phase2_Code_Detection_Quality.md`
- `DOCS/ROUTING/Implementation_SDD_Phase2.md` (this)

## Delta
- Introduced `RouteSignal` dataclass (for future scoring workflow).
- Replaced `CODE_STRUCT_REGEX` with a list `CODE_STRUCT_REGEXES` and updated call sites.
- Expanded `CODE_KEYWORDS` for broader language coverage.
- Preserved Phase 1 early-return priority semantics.

## Test Plan
- Run: `pytest -k phase2_code_quality -q`
- Ensure all Phase 1 tests still pass.

## Notes
- Full signal-scoring orchestration can land later without breaking current behavior.
