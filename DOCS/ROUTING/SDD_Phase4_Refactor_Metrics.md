
# SDD – Phase 4: Refactor & Observability

## Summary
Split routing heuristics into focused modules and add structured observability for decisions.

## Modules
- `llmc/routing/common.py` – `RouteSignal`, config loader, `record_decision`.
- `llmc/routing/code_heuristics.py` – fenced/structure/keyword scoring.
- `llmc/routing/erp_heuristics.py` – SKU/keyword scoring.

`llmc/routing/query_type.py` becomes a thin orchestrator that:
1. Normalizes input.
2. Loads routing config (`llmc.toml` if present).
3. Calls `code_heuristics.score_all` and `erp_heuristics.score_all`.
4. Resolves conflicts using policy (prefer code; configurable).
5. Emits a structured decision log.

## Config (`llmc.toml`)
```toml
[routing]
default_route = "docs"

[routing.code_detection]
# (future thresholds here)

[routing.erp_vs_code]
prefer_code_on_conflict = true
conflict_margin = 0.1
```

## Metrics
A JSON payload is logged via `logging.getLogger("llmc.routing")`:
- `route_name`, `confidence`, `reasons`
- `has_code`, `has_erp`, `text_len`

## Tests
- Tie-break preference via TOML.
- Basic behavior parity for code detection.
- Reasons present for observability.
