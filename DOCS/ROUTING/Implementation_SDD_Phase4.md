
# Implementation SDD – Phase 4 (Refactor & Observability)

## Touched Files
- `llmc/routing/query_type.py` (thin orchestrator)
- `llmc/routing/common.py` (new)
- `llmc/routing/code_heuristics.py` (new)
- `llmc/routing/erp_heuristics.py` (new)
- `tests/routing/test_query_type_phase4_refactor_and_metrics.py` (new)
- `DOCS/ROUTING/SDD_Phase4_Refactor_Metrics.md` (this)
- `DOCS/ROUTING/Implementation_SDD_Phase4.md` (this)

## Notes
- Maintains earlier reason tokens for backward compatibility (`priority:*`, `erp:*`, `conflict-policy:*`).
- Keeps defaults stable if `llmc.toml` is absent.
- Logging is best-effort and will not raise on failure.
