# SDD: Missing Test for 'route' CLI Command

## 1. Gap Description
The `llmc/cli.py` script includes a `route` command that is intended to test the domain resolution logic for a given file path. This is a critical function for the RAG (Retrieval-Augmented Generation) system, as it determines how files are processed. Currently, there are no dedicated tests to verify that this CLI command works as expected, including its ability to correctly parse arguments and display output.

## 2. Target Location
`tests/test_cli_entry_error_codes.py` can be extended to include this test, as it is related to testing CLI entry points. Alternatively, a new file `tests/test_cli_commands.py` could be created. Let's add it to `tests/test_cli_entry_error_codes.py` to keep related CLI tests together.

## 3. Test Strategy
The test will use `subprocess.run` to execute the `llmc/cli.py` script with the `route` command and a test file path. It will then capture the output and assert that the correct domain is printed. A separate test will verify the `--show-domain-decisions` flag.

## 4. Implementation Details
Two new test functions will be added to `tests/test_cli_entry_error_codes.py`.

```python
import subprocess
import sys
import pytest

# ... (existing code in the file)

def test_cli_route_command(tmp_path):
    """
    Test the 'route' CLI command for a basic routing decision.
    """
    # Create a dummy file to test routing on
    test_file = tmp_path / "pyproject.toml"
    test_file.write_text("[tool.poetry]")

    cli_script_path = "llmc/cli.py"

    result = subprocess.run(
        [sys.executable, cli_script_path, "route", "--test", str(test_file)],
        capture_output=True,
        text=True,
        cwd=tmp_path, # Run from tmp_path to ensure relative paths work
    )

    assert result.returncode == 0
    assert "Domain: [bold green]config[/bold green]" in result.stdout

def test_cli_route_command_show_reason(tmp_path):
    """
    Test the 'route' CLI command with the --show-domain-decisions flag.
    """
    test_file = tmp_path / "README.md"
    test_file.write_text("# My Project")

    cli_script_path = "llmc/cli.py"

    result = subprocess.run(
        [
            sys.executable,
            cli_script_path,
            "route",
            "--test",
            str(test_file),
            "--show-domain-decisions",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "Domain: [bold green]docs[/bold green]" in result.stdout
    assert "Reason: " in result.stdout
```
These tests will ensure the `route` command is functioning correctly from the command line. I'm using `tmp_path` to create a controlled environment for the tests.
