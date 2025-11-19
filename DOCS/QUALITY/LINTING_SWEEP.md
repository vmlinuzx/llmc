# Linting & Quality Sweep — Plan

This introduces a **Ruff-first** toolchain (lint + format) and a **baseline guard** so we can ratchet down violations without breaking velocity.

## What lands in this patch
- `pyproject.toml` with Ruff config (formatter enabled; Black optional later).
- `.pre-commit-config.yaml` to auto-fix (imports, pyupgrade, many E/F) before commit.
- `Makefile` targets: `lint`, `lint-fix`, `format`, `precommit`, `quality-baseline`, `quality-check`.
- `tools/dev/quality_baseline.py` to record and enforce **no regressions** from baseline.
- `tools/dev/safe_rewrites.py` single-purpose fixer for **bare `except:`** → `except Exception:`.

## Recommended rollout (fast)
1. **Record baseline** once on this branch:
   ```bash
   make quality-baseline
   ```
2. **Safe autofix (imports, pyupgrade, many E/F)**
   ```bash
   make lint-fix
   ```
3. **Dangerous category (manual / incremental)**
   - Undefined names (`F821`) — fix case-by-case.
   - Complex refactors — punt to feature branches/tests.
4. **Prevent backsliding** in CI:
   - Add a CI job: `make quality-check` (compares to baseline; fails if counts rise).

## CI snippet (GitHub Actions)
```yaml
name: quality
on: [push, pull_request]
jobs:
  ruff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install ruff pre-commit
      - run: make lint
      - run: make quality-check || true  # enable later after baseline is committed
```

## Safety notes
- `tools/dev/safe_rewrites.py` changes **only** the exact `except:` form. It will not touch `except BaseException:` or typed handlers.
- If you need Black, drop it later — Ruff-format is fine and avoids conflicts.

