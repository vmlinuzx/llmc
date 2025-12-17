# SDD: Missing Test for CLI Core Module Import Error

## 1. Gap Description
The `llmc/cli.py` script is designed to provide a user-friendly error message if the core `llmc` modules cannot be imported. This is a critical user experience feature for new users setting up the environment. However, there are no tests to verify that this error handling works correctly. The test should simulate an `ImportError` and assert that the expected error message is printed to standard output and the application exits with a non-zero status code.

## 2. Target Location
A new test file seems appropriate here, as there isn't a clear existing file for CLI tests of this nature. A good location would be `tests/test_cli_entry_error_codes.py` or a new file like `tests/test_cli_startup.py`. Given the existing file `test_cli_entry_error_codes.py`, I will add to that. The file seems to be for testing the CLI entry points and error codes, which is exactly what this test is for.

## 3. Test Strategy
The test will use `unittest.mock.patch` to temporarily remove a core `llmc` module from `sys.modules`, forcing an `ImportError` when `llmc/cli.py` is executed as a script. The test will then:
1.  Run `llmc/cli.py` as a subprocess.
2.  Capture `stdout` and `stderr`.
3.  Assert that the captured output contains the expected error message (e.g., "LLMC core modules not found").
4.  Assert that the subprocess exits with a status code of 1.

## 4. Implementation Details
A new test function, `test_cli_import_error_message`, will be added to `tests/test_cli_entry_error_codes.py`.

```python
import subprocess
import sys
import pytest

# ... (any existing code in the file)

def test_cli_import_error_message(monkeypatch):
    """
    Test that the CLI prints a helpful error and exits if core modules are missing.
    """
    # Simulate llmc.rag_nav not being available
    monkeypatch.setitem(sys.modules, "llmc.rag_nav.metadata", None)

    # The path to the script to run
    cli_script_path = "llmc/cli.py"

    # Run the script as a separate process
    result = subprocess.run(
        [sys.executable, cli_script_path, "monitor"],
        capture_output=True,
        text=True,
    )

    # Assert that it exits with an error code
    assert result.returncode == 1

    # Assert that the specific error message is shown to the user
    assert "LLMC core modules not found" in result.stdout
    assert "pip install" not in result.stdout # Ensure it's not the rich/typer error

```
This implementation assumes that `llmc/cli.py` can be run directly. If it's part of a larger `typer` app, the entry point might need to be invoked differently. Based on the `if __name__ == "__main__":` block, running it directly should work for testing purposes. I've chosen `monitor` as the command to run, but any command should trigger the import check.