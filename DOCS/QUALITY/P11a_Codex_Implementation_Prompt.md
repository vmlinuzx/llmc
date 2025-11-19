# P11a — Codex Implementation Prompt (Quality Scaffold)

1) Apply the patch (pyproject, pre-commit, Makefile, tools/dev scripts, docs).
2) Run:
   ```bash
   pip install ruff pre-commit
   make format
   make lint-fix
   python tools/dev/safe_rewrites.py
   make quality-baseline
   ```
3) Commit results.

Git best practices:
- Branch: `chore/quality-p11a-ruff-baseline`
- Commit: `chore(quality): add Ruff, pre-commit, baseline guard + safe bare-except rewrite`

