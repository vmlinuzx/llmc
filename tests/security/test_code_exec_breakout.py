"""
Tests for code_exec security properties.

These tests verify security behaviors after the subprocess isolation fix.
The old exec() model had vulnerabilities; the new subprocess model fixes them.
"""

import time
from unittest.mock import MagicMock

from llmc_mcp.isolation import is_isolated_environment
from llmc_mcp.tools.code_exec import execute_code


def test_code_exec_env_via_stdout(monkeypatch):
    """
    Test that subprocess can access environment variables.
    
    NOTE: This is expected behavior - subprocess inherits parent's env.
    The fix is that the subprocess can't access parent's MEMORY (globals,
    tool_caller, credentials in Python objects). Env vars are replicated
    to subprocess at spawn time.
    
    To prevent env var leakage, run in Docker with explicit env allowlist.
    """
    is_isolated_environment.cache_clear()
    monkeypatch.setenv("MY_TEST_VAR", "test_value_123")
    monkeypatch.setenv("LLMC_ISOLATED", "1")

    # Use stdout since _result_ is not available in subprocess mode
    payload = """
import os
print(os.environ.get("MY_TEST_VAR", "NOT_FOUND"))
"""

    result = execute_code(code=payload, tool_caller=MagicMock(), timeout=5)

    assert result.success is True
    assert "test_value_123" in result.stdout
    # return_value is always None in subprocess mode
    assert result.return_value is None


def test_code_exec_in_process_namespace_not_accessible(monkeypatch):
    """
    Verify that in-process namespace variables are NOT accessible.
    
    In the old exec() model, _result_ was directly accessible because
    code ran in the same process. In subprocess mode, code runs in a
    separate process and can't access any parent process variables.
    """
    is_isolated_environment.cache_clear()
    monkeypatch.setenv("LLMC_ISOLATED", "1")

    payload = """
# Try to access tool_caller - would have worked in old exec() model
try:
    print(f"tool_caller: {tool_caller}")
except NameError:
    print("tool_caller: NOT_ACCESSIBLE")
    
# Try _result_ assignment - doesn't affect parent anymore
_result_ = "this_wont_work"
print("_result_ set in subprocess")
"""

    result = execute_code(code=payload, tool_caller=MagicMock(), timeout=5)

    assert result.success is True
    assert "tool_caller: NOT_ACCESSIBLE" in result.stdout
    # _result_ won't propagate back to parent
    assert result.return_value is None


def test_code_exec_timeout_works(monkeypatch):
    """
    Test that timeout actually works with subprocess isolation.
    
    The old exec() model ran in the main thread and timeout was ignored.
    The new subprocess model properly enforces timeout.
    """
    is_isolated_environment.cache_clear()
    monkeypatch.setenv("LLMC_ISOLATED", "1")

    start_time = time.time()

    payload = """
import time
time.sleep(10)  # Try to sleep for 10 seconds
print("Sleep completed")  # Should never print
"""

    # Set 1 second timeout
    result = execute_code(code=payload, tool_caller=MagicMock(), timeout=1)
    
    duration = time.time() - start_time

    # With subprocess, timeout should be enforced
    # Should take ~1s (timeout), not ~10s (full sleep)
    assert duration < 5.0, f"Timeout not enforced! Duration: {duration}s"
    
    # Should have timed out
    assert result.success is False
    assert "timed out" in result.error.lower()


def test_code_exec_isolates_pids(monkeypatch):
    """
    Verify code runs in a subprocess with different PID.
    
    This confirms process isolation - code can't share memory with parent.
    """
    is_isolated_environment.cache_clear()
    monkeypatch.setenv("LLMC_ISOLATED", "1")

    import os
    parent_pid = os.getpid()

    payload = f"""
import os
child_pid = os.getpid()
print(f"child_pid={{child_pid}}")
print(f"parent_pid={parent_pid}")
print(f"isolated={{child_pid != {parent_pid}}}")
"""

    result = execute_code(code=payload, tool_caller=MagicMock(), timeout=5)

    assert result.success is True
    assert "isolated=True" in result.stdout
