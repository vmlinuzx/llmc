# SDD: Incomplete Path Traversal Check in `route` Command

## 1. Gap Description
The `route` command in `llmc/cli.py` has a security check to prevent path traversal. The current check (`if ".." in test or ".." in Path(test).parts:`) is basic and may not cover all forms of path traversal attacks. The existing test only covers a simple `../` case. More sophisticated attacks could bypass this check.

## 2. Target Location
`tests/cli/test_cli.py`

## 3. Test Strategy
The test strategy is to add more comprehensive test cases to `test_route_path_traversal` or create a new parameterized test to cover various path traversal payloads. These tests should be added to `tests/cli/test_cli.py`.

The `CliRunner` from `typer.testing` should be used to invoke the `route` command with malicious inputs. The test should assert that the command exits with a non-zero status code and prints a security error message.

## 4. Implementation Details
A new test function, `test_route_path_traversal_more_cases`, should be added to `tests/cli/test_cli.py`. It should be parameterized to test multiple malicious inputs.

Example traversal payloads to test:
- Absolute paths: `/etc/passwd`
- Absolute paths with `..`: `/var/log/../log/messages`
- URL-encoded traversal: `%2e%2e%2f` (if typer/click decodes it)
- Nested traversal: `foo/bar/../../../../etc/passwd`

The test should look like this:
```python
import pytest
from typer.testing import CliRunner
from llmc.cli import app

runner = CliRunner()

@pytest.mark.parametrize(
    "path_input",
    [
        "../secret.txt",
        "foo/../../bar.txt",
        "/etc/passwd",
        "foo/bar/../../../etc/passwd",
    ],
)
def test_route_path_traversal_variations(path_input):
    """Test that various path traversal attempts are rejected."""
    result = runner.invoke(app, ["route", "--test", path_input])
    assert result.exit_code != 0
    assert "Security Error: Path traversal detected" in result.stdout
```

This will replace the existing `test_route_path_traversal` to avoid redundancy and create a more robust test suite. The new test should be added and the old one should be removed.
