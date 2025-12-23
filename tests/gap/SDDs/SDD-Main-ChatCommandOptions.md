# SDD: Missing Tests for `chat` Command Options

## 1. Gap Description
The `chat` command in `llmc/main.py` has several options (`--new`, `--recall`, `--list`, etc.) that are passed to the `llmc_agent.cli.main` function. However, there are no tests to verify that these options are correctly passed and that they have the intended effect.

This SDD describes the tests required to validate the `chat` command options.

## 2. Target Location
`tests/main/test_main.py`

## 3. Test Strategy
The tests will use `pytest` and `typer.testing.CliRunner` to invoke the `chat` command with different options and verify that the `llmc_agent.cli.main` function is called with the correct arguments. The tests will cover the following scenarios:
- **`--new` option:** Invoke the `chat` command with the `--new` option and verify that the `-n` flag is passed to `llmc_agent.cli.main`.
- **`--recall` option:** Invoke the `chat` command with the `--recall` option and verify that the `-r` flag is passed to `llmc_agent.cli.main`.
- **`--list` option:** Invoke the `chat` command with the `--list` option and verify that the `-l` flag is passed to `llmc_agent.cli.main`.

## 4. Implementation Details
The test implementation will require the following:
- Extend the existing test file `tests/main/test_main.py`.
- `typer.testing.CliRunner` to invoke the `chat` command.
- `unittest.mock.patch` to mock the `llmc_agent.cli.main` function and inspect the arguments passed to it.
- Test cases for each of the scenarios described in the Test Strategy.
- Assertions that the `llmc_agent.cli.main` function is called with the correct arguments.
