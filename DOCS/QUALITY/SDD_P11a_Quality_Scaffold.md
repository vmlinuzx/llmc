# SDD — P11a Quality Scaffold (Ruff + Baseline + Safe Rewrites)

**Goal:** Stop the upward trend in lint violations (now 406) and create a sustainable path to reduce them without blocking shipping.

## Deliverables
- Ruff config in `pyproject.toml`
- Pre-commit hooks
- Baseline capture & regression check
- Safe rewrite for bare `except:`

## Non-goals
- Fix all undefined names in one patch.
- Enforce zero warnings overnight.

