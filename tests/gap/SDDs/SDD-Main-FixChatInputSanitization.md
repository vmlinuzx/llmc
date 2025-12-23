# SDD: Implement Input Sanitization for `chat` Command

## 1. Gap Description
The `chat` command in `llmc/main.py` is vulnerable to injection attacks as it passes user input directly to the `llmc_agent.cli.main` function. The tests implemented in `tests/main/test_main.py` demonstrate this vulnerability.

This SDD describes the necessary changes to implement input sanitization for the `chat` command.

## 2. Target Location
`llmc/main.py`

## 3. Test Strategy
The existing tests in `tests/main/test_main.py` will be used to validate the fix. The tests should pass after the sanitization logic is implemented.

## 4. Implementation Details
The implementation will require the following:
- Modify the `chat` command in `llmc/main.py`.
- Add a sanitization function that removes or escapes potentially malicious characters from the `prompt` argument before passing it to the `llmc_agent.cli.main` function.
- A simple sanitization approach would be to use a library like `bleach` or to implement a custom function that removes characters like `;`, `<`, `>`, `'`, and `--`.
- The goal is to ensure that the tests in `tests/main/test_main.py` pass.
