
# Implementation SDD – Phase 1, Change 1 (Normalize Input)

## Touched Files
- `llmc/routing/query_type.py`
- `tests/routing/test_query_type_phase1_change1.py`
- `DOCS/ROUTING/SDD_Phase1_Change1_NormalizeInput.md` (this doc)
- `DOCS/ROUTING/Implementation_SDD_Phase1_Change1.md` (this doc)

## Delta
- Inserted a normalization block at the top of `classify_query`:
  - Handles `None`, non-string inputs, and whitespace-only strings.
  - Early return to route `docs` with `confidence=0.2` and reason `empty-or-none-input`.

## Test Plan
- `pytest -k phase1_change1` should pass.
- Two tests validate:
  - `classify_query(None)` returns docs, low confidence, and reason contains `empty-or-none-input`.
  - `classify_query("   \n\t")` returns docs, low confidence, and same reason token.

## Rollback
- Revert the inserted block if unexpected behavior arises; tests are additive and may be left in place.

## Notes
- Type annotation for `text` remains `str` in the file to minimize signature churn; the logic accepts `None`. If you prefer strict typing, change the signature to `Optional[str]` and update call sites.
