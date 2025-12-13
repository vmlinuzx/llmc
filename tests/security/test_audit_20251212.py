
import pytest
from unittest.mock import patch, MagicMock
from llmc_agent.backends.llmc import LLMCBackend
from llmc_mcp.tools.code_exec import execute_code
import os
import signal
import time
import threading

# --- POC 1: Argument Injection in LLMCBackend ---

@pytest.mark.asyncio
async def test_poc_llmc_agent_arg_injection(tmp_path):
    """
    VULNERABILITY: Argument Injection in LLMCBackend.
    The 'query' argument is passed directly to 'rg' without '--'.
    If query starts with '-', it's treated as a flag.
    """
    # Create fake repo root
    (tmp_path / "llmc.toml").touch()
    
    backend = LLMCBackend(repo_root=tmp_path)
    
    # Mock subprocess.run to capture arguments
    with patch("subprocess.run") as mock_run:
        # Simulate a failing LLMC check to force fallback to rg
        mock_run.side_effect = [
            # 1. check_llmc_available -> fails
            FileNotFoundError(), 
            # 2. _fallback_search -> capture this
            MagicMock(returncode=0, stdout="") 
        ]
        
        # Attack payload: a flag that rg understands
        payload = "--version"
        
        await backend.search(payload)
        
        # Check the call arguments
        calls = mock_run.call_args_list
        # We might have extra calls if check_llmc_available is called multiple times or differently
        # But we expect at least one call to rg (which should be the last one if we only did one search)
        
        found_rg_call = False
        for call in calls:
            args, _ = call
            cmd_list = args[0]
            if cmd_list[0] == "rg":
                found_rg_call = True
                print(f"\n[DEBUG] rg command: {cmd_list}")
                if payload in cmd_list:
                    try:
                        payload_idx = cmd_list.index(payload)
                        # Check if '--' is before payload
                        has_separator = "--" in cmd_list and cmd_list.index("--") < payload_idx
                        
                        if not has_separator:
                            pytest.fail(f"VULNERABILITY CONFIRMED: Argument '{payload}' treated as flag. Command: {cmd_list}")
                    except ValueError:
                        pass
        
        if not found_rg_call:
             pytest.fail("Test Setup Error: 'rg' was never called.")

# --- POC 2: Code Execution DoS (Infinite Loop) ---

def test_poc_code_exec_dos():
    """
    VULNERABILITY: DoS in execute_code.
    exec() runs in the main thread. There is NO timeout mechanism for the Python code itself.
    The 'timeout' parameter in execute_code() only catches subprocess.TimeoutExpired,
    which is NOT raised by standard exec().
    """
    
    # We need to run this in a separate thread/process to not hang the test runner forever
    # But for the POC, we can just inspect the code logic or try a short blocking call
    
    # Mock require_isolation to bypass the check
    with patch("llmc_mcp.isolation.require_isolation"):
        
        # The vulnerable code:
        # try:
        #    exec(compiled, namespace)
        # except subprocess.TimeoutExpired: ...
        
        # If we run "import time; time.sleep(2)", it WILL sleep for 2 seconds.
        # If timeout was working, it should interrupt it (if timeout=1).
        # But you can't interrupt a thread easily in Python.
        
        start = time.time()
        # Use busy loop to bypass pytest_ruthless time.sleep mock
        code = """
import time
start = time.time()
while time.time() - start < 2:
    pass
"""
        start = time.time()
        result = execute_code(
            code=code,
            tool_caller=lambda n, a: None,
            timeout=1  # Request 1s timeout
        )
        end = time.time()
        
        duration = end - start
        print(f"\n[DEBUG] Execution took {duration:.2f}s (requested timeout: 1s)")
        print(f"[DEBUG] Result: {result}")
        
        if duration >= 2.0:
             pytest.fail(f"VULNERABILITY CONFIRMED: execute_code failed to enforce timeout. Took {duration:.2f}s > 1s")

# --- POC 3: Process State Corruption ---

def test_poc_code_exec_environ_leak():
    """
    VULNERABILITY: Shared Process State.
    execute_code() runs in the same process. Modifying os.environ affects the host.
    """
    
    # Mock require_isolation
    with patch("llmc_mcp.isolation.require_isolation"):
        
        key = "VULN_TEST_KEY"
        val = "pwned"
        
        # Ensure clean state
        if key in os.environ:
            del os.environ[key]
            
        code = f"import os; os.environ['{key}'] = '{val}'"
        
        execute_code(
            code=code,
            tool_caller=lambda n, a: None
        )
        
        # Check if environment leaked to host
        if os.environ.get(key) == val:
            del os.environ[key] # cleanup
            pytest.fail("VULNERABILITY CONFIRMED: execute_code modified host process environment variables.")

