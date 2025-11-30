
# Implementation SDD – Phase 1, Change 2 (Priority Order)

## Touched Files
- `llmc/routing/query_type.py`
- `tests/routing/test_query_type_phase1_change2_priority.py`
- `DOCS/ROUTING/SDD_Phase1_Change2_PriorityOrder.md`
- `DOCS/ROUTING/Implementation_SDD_Phase1_Change2.md`

## Delta
- Inserted an early-return priority block into `classify_query`:
  - Fenced code → `route_name="code"`, `confidence=0.95`.
  - Code structure → `route_name="code"`, `confidence=0.90`.
  - Code keywords → `route_name="code"`, `confidence=0.70`.

## Tests
- Three tests ensure code (fence/structure/keywords) is chosen **before** ERP.

## Rollback
- Remove the priority block; tests can remain as pending if behavior reverts intentionally.
