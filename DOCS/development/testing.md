# Testing Guide

Reliable testing is critical for LLMC, especially given the "Ruthless Testing" philosophy.

## Running Tests

### Standard Test Suite

Run the full test suite using `pytest`:

```bash
python3 -m pytest
```

### Targeted Testing

Run tests for specific components:

```bash
# RAG components
python3 -m pytest llmc/rag/tests/

# MCP tools
python3 -m pytest tests/mcp/

# Security tests (requires extra deps)
python3 -m pytest tests/security/
```

### Gap Analysis Tests

We maintain "Gap Tests" that document known limitations or missing features. These are expected to fail until the feature is implemented.

```bash
python3 -m pytest tests/gap/
```

## Test Structure

- `tests/`: High-level integration and system tests.
- `llmc/*/tests/`: Unit tests co-located with the code (e.g., `llmc/rag/tests`).
- `tests/security/`: Security-specific regression tests.
- `tests/gap/`: Tests that document missing functionality.

## Writing Tests

1.  **Use Pytest:** We use standard `pytest` fixtures and assertions.
2.  **Mock External Calls:** LLM calls and network requests must be mocked.
3.  **Ruthless Mode:** The test runner (`tests/_plugins/pytest_ruthless.py`) patches `time.sleep` to fail tests that rely on arbitrary waits. Use deterministic synchronization (polling with timeout) instead.

## Environment

Ensure you have the development dependencies installed:

```bash
pip install -e ".[dev,rag,tui,agent]"
```
