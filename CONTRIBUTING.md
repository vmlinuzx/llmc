# Contributing to LLMC

Thanks for considering contributing to LLMC. This was originally a personal tool to solve my token cost problem, but I'm opening it up because maybe it'll help others too.

## Quick Overview

- **Issues:** Report bugs, request features, ask questions
- **Pull Requests:** Fork → branch → PR → review → merge
- **Code Style:** We use Ruff for linting and formatting
- **Tests:** pytest with good coverage expected

## Getting Started

1. **Fork the repo** on GitHub
2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR-USERNAME/llmc.git
   cd llmc
   ```
3. **Set up your environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[rag]"
   ```
4. **Create a feature branch:**
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

## Branch Naming

- `feat/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation only
- `refactor/` - Code refactoring
- `test/` - Test additions or fixes
- `chore/` - Maintenance tasks

## Before You Submit

### 1. Run Tests
```bash
pytest
```

All tests should pass. If you're adding new functionality, add tests for it.

### 2. Run Linting
```bash
ruff check .
ruff format .
```

Fix any issues Ruff complains about.

### 3. Update Documentation
- If you change behavior, update relevant docs in `DOCS/`
- If you add a CLI command, document it
- If you add a feature, consider updating the README

## Pull Request Process

1. **Push your branch** to your fork
2. **Open a PR** against `main` with:
   - Clear title describing what you did
   - Description explaining why (not just what)
   - Link any related issues
3. **Wait for review**
   - I'll review when I can (remember, this is a side project)
   - Be open to feedback and iteration
4. **Merge** happens after approval

### Good PR Titles
- ✅ `feat: add semantic caching for embeddings`
- ✅ `fix: daemon crashes on missing config file`
- ✅ `docs: clarify enrichment chain configuration`
- ❌ `update stuff`
- ❌ `fixes`

## Code Style

We use **Ruff** for both linting and formatting. Configuration is in `pyproject.toml`.

Key conventions:
- **Line length:** 100 characters
- **Quotes:** Double quotes for strings
- **Imports:** Sorted via isort (handled by Ruff)
- **Type hints:** Encouraged but not strictly required everywhere
- **Docstrings:** For public APIs and non-obvious functions

## Testing Guidelines

- **Unit tests:** Test individual functions/classes in isolation
- **Integration tests:** Test interactions between components
- **E2E tests:** Test full workflows (sparingly - they're slow)
- **Test files:** Live in `tests/` and start with `test_`
- **Fixtures:** Use pytest fixtures from `conftest.py`

### Running Specific Tests
```bash
pytest tests/test_specific_file.py
pytest tests/test_file.py::test_specific_function
pytest -k "keyword"  # Run tests matching keyword
```

## Documentation

- **Code comments:** Explain WHY, not what. The code shows what.
- **AGENTS.md:** Behavioral guidelines for LLM agents working in this repo
- **CONTRACTS.md:** Environment and policy contracts
- **DOCS/:** Deep dive documentation for specific subsystems

## What Makes a Good Contribution?

**Great contributions:**
- Solve a real problem you encountered
- Include tests that prove it works
- Are scoped reasonably (not rewriting half the codebase)
- Follow existing patterns in the codebase
- Have clear commit messages

**Less great contributions:**
- "I think this would be cool" without a use case
- Massive refactors that touch everything
- No tests or documentation
- Break existing functionality

## Questions?

Open an issue with your question. I'm happy to help clarify how things work or discuss potential contributions before you write code.

## Code of Conduct

**TL;DR:** Don't be a dick. Be professional, be respectful, be helpful.

We're all here to solve problems and learn. If you can't engage constructively, this probably isn't the place for you.

## License

By contributing, you agree that your contributions will be licensed under the MIT License (same as the project).
