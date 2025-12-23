# SDD: Missing Tests for `route` Command

## 1. Gap Description
The `route` command in `llmc/cli.py` is a `typer` command that resolves the domain of a given file path. However, there are no tests to verify its behavior, especially for invalid or malicious file paths.

This SDD describes the tests required to validate the `route` command.

## 2. Target Location
`tests/cli/test_cli.py`

## 3. Test Strategy
The tests will use `pytest` and `typer.testing.CliRunner` to invoke the `route` command and assert its output. The tests will cover the following scenarios:
- **Valid File Path:** Pass a valid file path and verify that the command outputs the correct domain.
- **Invalid File Path:** Pass an invalid file path and verify that the command handles the error gracefully.
- **File Path with Traversal:** Pass a file path with traversal attempts (`../`) and verify that the command does not execute and reports an error.

## 4. Implementation Details
The test implementation will require the following:
- A new test file `tests/cli/test_cli.py` or extend the existing one.
- `typer.testing.CliRunner` to invoke the `route` command.
- Test cases for each of the scenarios described in the Test Strategy.
- Assertions on the command's output and exit code.