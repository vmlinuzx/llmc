# SDD: Missing Test for `search` Command

## 1. Gap Description
The `search` command in `llmc/cli.py` is a placeholder demo command. While it has no real logic, it is an exposed CLI endpoint. There is no test to ensure that invoking this command works as expected and doesn't raise an unexpected exception.

## 2. Target Location
`tests/cli/test_cli.py`

## 3. Test Strategy
A simple test will be added using the `CliRunner` from `typer.testing`. The test will invoke the `search` command with a sample query. It will then assert that the command exits with a `0` status code and that the expected "Searching for..." text is present in the output.

## 4. Implementation Details
A new test function `test_search_command()` should be added to `tests/cli/test_cli.py`.

```python
from typer.testing import CliRunner
from llmc.cli import app

runner = CliRunner()

def test_search_command():
    """Test that the demo search command runs without error."""
    result = runner.invoke(app, ["search", "test query"])
    assert result.exit_code == 0
    assert "Searching for test query..." in result.stdout
```

This ensures that the command remains a valid, non-crashing part of the CLI.
