
# Ruthless Testing Agent — Guardrails & Playbook

**Date:** 2025-11-19

This bundle gives your ruthless testing agent firm guardrails and a clean playbook.

## What you get
- `tests/_plugins/pytest_ruthless.py` — pytest plugin that:
  - **Blocks network** by default (socket/requests), allow via `--allow-network` or `@pytest.mark.allow_network`.
  - **Bans sleep** (`time.sleep`) by default, allow via `--allow-sleep` or `@pytest.mark.allow_sleep`.
  - Seeds randomness deterministically.
  - Registers useful markers.
- `tests/_utils/envelopes.py` — helpers to assert RAG tool envelopes.
- `tests/conftest.py` — hermetic env & auto-fixtures wired to the plugin.
- `pytest.ini` — sensible defaults + marker registration.
- `tests/_examples/test_nav_template.py` — a good table-driven example (not executed by default).

## Usage (copy/paste)
```bash
git checkout -b test/guardrails-ruthless
git apply --reject --whitespace=fix patches/0001-tests-guardrails-ruthless.patch
pytest -q
```

## Quick rules recap
1. Every test asserts `meta.status`, `source`, `freshness_state`.
2. Table-drive with `@pytest.mark.parametrize`.
3. Hermetic by default (tmp dirs, no network).
4. Mirror every OK case with a FAIL/FALLBACK case.
5. Determinism: seed RNG, avoid time-based tests.

