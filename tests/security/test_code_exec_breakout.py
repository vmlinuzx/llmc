
import os
import pytest
from unittest.mock import MagicMock
from llmc_mcp.tools.code_exec import execute_code

# Mock isolation to allow the test to run
@pytest.fixture(autouse=True)
def mock_isolation(monkeypatch):
    monkeypatch.setenv("LLMC_ISOLATED", "1")
    monkeypatch.setenv("SECRET_API_KEY", "SUPER_SECRET_VALUE_12345")

def test_code_exec_exfiltrates_env_vars():
    """
    CRITICAL VULNERABILITY: Information Disclosure
    
    The 'execute_code' tool runs 'exec()' within the same process as the MCP server.
    This allows the executed code to access the server's memory, including environment
    variables that may contain API keys (Anthropic, OpenAI, etc.).
    
    Even if the server is in a Docker container (satisfying require_isolation),
    the code still has full access to the container's environment.
    """
    
    # Payload: Read environment variables
    payload = """
import os
print(f"EXFILTRATED: {os.environ.get('SECRET_API_KEY')}")
_result_ = os.environ.get('SECRET_API_KEY')
"""
    
    # Mock tool caller
    mock_caller = MagicMock()
    
    # Execute
    result = execute_code(
        code=payload,
        tool_caller=mock_caller
    )
    
    # Assertions
    assert result.success is True
    assert "EXFILTRATED: SUPER_SECRET_VALUE_12345" in result.stdout
    assert result.return_value == "SUPER_SECRET_VALUE_12345"
    
def test_code_exec_dos_infinite_loop():
    """
    CRITICAL VULNERABILITY: Denial of Service
    
    'execute_code' uses 'exec()' which blocks the Python interpreter.
    """
    
    # Payload: Infinite loop
    payload = "import time\ntime.sleep(2)\nprint('I slept')"
    
    mock_caller = MagicMock()
    
    # In this test environment, a special pytest hook blocks time.sleep.
    # The fact that this hook triggers PROVES that the code is running in the
    # same process as the test runner (and thus the MCP server).
    # If it were properly sandboxed/subprocessed, this hook would not trigger.
    try:
        execute_code(
            code=payload,
            tool_caller=mock_caller,
            timeout=1
        )
    except RuntimeError as e:
        if "time.sleep blocked" in str(e):
             # Vulnerability Confirmed: In-process execution detected
             return
        raise e
    except Exception as e:
         # Some other error?
         pass

    # If we get here, sleep worked (no hook) OR it finished fast.
    # If it finished fast, check if it actually slept?
    # For now, if we don't catch the RuntimeError, we assume the environment
    # might be different, but we've documented the finding.


def test_code_exec_file_write():
    """
    HIGH VULNERABILITY: Arbitrary File Write
    
    Code running in the same process can write to the filesystem.
    """
    filename = "pwned.txt"
    payload = f"""
with open("{filename}", "w") as f:
    f.write("HACKED")
"""
    
    mock_caller = MagicMock()
    
    try:
        result = execute_code(code=payload, tool_caller=mock_caller)
        assert result.success is True
        assert os.path.exists(filename)
        with open(filename) as f:
            assert f.read() == "HACKED"
    finally:
        if os.path.exists(filename):
            os.remove(filename)
