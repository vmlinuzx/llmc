# SDD – Phase 3: ERP & Fence Edge Cases + Conflict Policy

## Goals
- Harden ERP vs code conflicts (SKU/ID patterns and keywords).
- Robust fence detection in play from Phase 1 Change 3.
- Add conflict policy knobs via TOML and env overrides.

### TOML
```toml
[routing.erp_vs_code]
prefer_code_on_conflict = true
conflict_margin = 0.1
```

### Env overrides
- `LLMC_ROUTING_PREFER_CODE_ON_CONFLICT` (true/false)
- `LLMC_ROUTING_CONFLICT_MARGIN` (float)
