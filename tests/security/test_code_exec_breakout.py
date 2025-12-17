import time
from unittest.mock import MagicMock

from llmc_mcp.isolation import is_isolated_environment
from llmc_mcp.tools.code_exec import execute_code


def test_code_exec_exfiltration(monkeypatch):
    """
    VULN-001: Environment Variable Exfiltration
    Demonstrates that execute_code running in-process allows reading
    sensitive environment variables (API keys) of the host process.
    """
    is_isolated_environment.cache_clear()
    monkeypatch.setenv("LLMC_MCP_API_KEY", "SUPER_SECRET_KEY_123")
    monkeypatch.setenv("LLMC_ISOLATED", "1")

    payload = """
import os
_result_ = os.environ.get("LLMC_MCP_API_KEY")
"""

    result = execute_code(code=payload, tool_caller=MagicMock(), timeout=1)

    assert result.success is True
    assert result.return_value == "SUPER_SECRET_KEY_123"


def test_code_exec_blocks_main_thread(monkeypatch):
    """
    VULN-002: DoS via Main Thread Blocking
    Demonstrates that execute_code blocks the main thread, ignoring the timeout
    parameter (because it uses exec() instead of subprocess).
    """
    is_isolated_environment.cache_clear()
    monkeypatch.setenv("LLMC_ISOLATED", "1")

    start_time = time.time()

    payload = """
import time
time.sleep(2)
"""

    print("\n[Test] Executing sleep payload...")
    result = execute_code(code=payload, tool_caller=MagicMock(), timeout=1)
    print(
        f"[Test] Execution finished. Result success: {result.success}, Error: {result.error}"
    )

    duration = time.time() - start_time

    # If it blocked, duration should be ~2s
    # If it was properly isolated/async, it might be less or handle timeout differently
    assert duration >= 2.0
    assert result.error is None
