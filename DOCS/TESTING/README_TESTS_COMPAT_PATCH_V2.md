# Tests Compatibility & Guardrails Patch — v2
**Date:** 2025-11-19

Fixes remaining blockers:

- FileExistsError storms: numbered tmp dirs + safe `Path.mkdir` inside pytest tmp roots.
- String division TypeError: provides a `compat_path_join(a,b)` helper in `builtins` for tests or modules to adopt quickly.
- CLI import mismatch: legacy `tools.rag_repo.cli` re-export added to package init.
- Enrichment requests stub: now includes `.post/.get/.put/.patch/.delete` and `.Session` with same methods.
- Unknown marks: registered in `pytest.ini` and also in plugin as a safety net.

Apply:
```bash
git checkout -b fix/tests-compat-guardrails-v2
git apply --reject --whitespace=fix patches/0001-tests-compat-guardrails-v2.patch
pytest --basetemp="$(mktemp -d)" -q
```
