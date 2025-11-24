.PHONY: lint lint-fix format precommit install-precommit quality-baseline quality-check test

lint:
	python -m ruff check .

lint-fix:
	python -m ruff check . --fix

format:
	python -m ruff format .

install-precommit:
	pre-commit install

precommit:
	pre-commit run -a

quality-baseline:
	python tools/dev/quality_baseline.py write

quality-check:
	python tools/dev/quality_baseline.py check

test:
	python -m ruff check .
	python -m mypy --ignore-missing-imports scripts/qwen_enrich_batch.py
	pytest
