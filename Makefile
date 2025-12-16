.PHONY: lint lint-fix format precommit install-precommit quality-baseline quality-check test docs docs-serve

lint:
	python3 -m ruff check .

lint-fix:
	python3 -m ruff check . --fix

format:
	python3 -m ruff format .

install-precommit:
	pre-commit install

precommit:
	pre-commit run -a

quality-baseline:
	python3 tools/dev/quality_baseline.py write

quality-check:
	python3 tools/dev/quality_baseline.py check

test:
	python3 -m ruff check .
	python3 -m mypy --ignore-missing-imports scripts/qwen_enrich_batch.py
	pytest

# === Documentation ===

docs:
	@echo "Generating reference documentation..."
	python3 scripts/generate_cli_docs.py
	python3 scripts/generate_config_docs.py
	.venv/bin/python3 scripts/generate_mcp_docs.py
	@echo "Done. Run 'make docs-serve' to preview."

docs-serve:
	@echo "Starting MkDocs dev server..."
	mkdocs serve

docs-build:
	mkdocs build --strict

