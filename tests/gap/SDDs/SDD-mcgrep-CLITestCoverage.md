# SDD: mcgrep CLI Test Coverage

## 1. Gap Description

The `mcgrep` command-line tool, a key entry point for semantic search, currently lacks any automated tests. This gap means there is no validation for its argument parsing, command dispatch, various output modes (`--extract`, `--expand`), or error handling paths (e.g., when run outside a repository or when an index is missing).

Without tests, regressions in the CLI behavior can go undetected.

## 2. Target Location

A new test file should be created at: `tests/cli/test_mcgrep.py`

## 3. Test Strategy

The testing will be done using `typer.testing.CliRunner` to invoke the `mcgrep` CLI in a controlled environment. The strategy involves a combination of unit tests for helper functions and integration tests for the CLI commands.

### 3.1. Unit Tests

The small, pure helper functions in `mcgrep.py` should be tested directly.
- `_format_source_indicator`: Test different source and freshness combinations.
- `_normalize_result_path`: Test with absolute, relative, and invalid paths.
- `_merge_line_ranges`: Test with empty lists, single ranges, overlapping ranges, and adjacent ranges.

### 3.2. Integration Tests (CLI)

A `CliRunner` will be used to execute `mcgrep` with various arguments. Key backend services (like the actual search and service commands) should be mocked using `unittest.mock.patch` to isolate the CLI logic.

- **Setup**: A pytest fixture should set up a temporary directory structure mimicking an llmc repository, including a dummy config and a mock index if needed.
- **Default Behavior**:
    - Test `mcgrep` with no arguments to ensure it prints the custom help message.
    - Test `mcgrep "query"` to ensure it correctly invokes the `search` command.
- **`search` Command**:
    - Mock `llmc.rag.search.search_spans` to return predictable results.
    - Test a basic query and verify the output format.
    - Test with mutually exclusive options like `--extract` and `--expand` to ensure `BadParameter` is raised.
    - Test error conditions, like mocking `find_repo_root` to raise an exception, and verify the correct error message is printed.
    - Test the `--emit-training` flag.
- **Other Commands (`status`, `watch`, `init`, `stop`)**:
    - Mock the underlying functions (e.g., `llmc.commands.service.start`, `llmc.rag.doctor.run_rag_doctor`).
    - Invoke each command (`mcgrep status`, `mcgrep watch`, etc.).
    - Assert that the mocked function was called once.

## 4. Implementation Details

- Use `pytest` as the test framework.
- Use `typer.testing.CliRunner` for invoking the CLI.
- Use `unittest.mock` for patching backend functions.
- Create fixtures to manage temporary file systems and mock data.
- The new test file should be `tests/cli/test_mcgrep.py`.
- Tests should be written in a clear, descriptive manner, with one test function per distinct behavior.
