# SDD: MCP Command Injection & Blacklist

## 1. Gap Description
The `run_cmd` tool relies on `subprocess.run(shell=False)` and a blacklist. We need to verify that:
1.  Shell injection characters (`;`, `|`, `&&`) are treated as literal arguments, not operators (verifying `shell=False`).
2.  The blacklist mechanism correctly blocks specified binaries.
3.  The *default* blacklist is empty (documenting the risk).

## 2. Target Location
`tests/mcp/test_cmd_security.py`

## 3. Test Strategy
1.  **Test Case 1 (Injection)**: Run `run_cmd("echo hello; echo injected", cwd=., blacklist=[])`.
    *   **Expectation**: Output should be `hello; echo injected` (literals) NOT `hello\ninjected` (execution).
2.  **Test Case 2 (Blacklist)**: Run `run_cmd("python script.py", cwd=., blacklist=["python"])`.
    *   **Expectation**: Fail with security error.
3.  **Test Case 3 (Bypass Attempt)**: Run `run_cmd("/usr/bin/python script.py", cwd=., blacklist=["python"])`.
    *   **Expectation**: Fail (should check basename).

## 4. Implementation Details
-   Use `llmc_mcp.tools.cmd.run_cmd`.
-   Use `shutil.which("echo")` or similar to find a safe binary for the injection test, or just use `ls`. `echo` is a shell built-in often but usually available as `/bin/echo`. `ls` is safer.

```python
import pytest
import shutil
from llmc_mcp.tools.cmd import run_cmd

def test_shell_injection_prevention(tmp_path):
    # Try to chain commands
    # If shell=True, this would create the file 'pwned'
    # If shell=False, it tries to list a file named "; touch pwned"
    
    pwn_file = tmp_path / "pwned"
    
    # We use 'ls' or 'echo'. 
    # 'echo hello; touch pwned' -> 
    #   shell=False: prints "hello; touch pwned"
    #   shell=True: prints "hello", creates file
    
    res = run_cmd(f"echo 'hello; touch {pwn_file}'", cwd=tmp_path, blacklist=[])
    
    assert not pwn_file.exists(), "Command injection succeeded! File was created."
    # The output should contain the literal characters
    assert ";" in res.stdout or ";" in res.stderr or "not found" in res.stderr

def test_blacklist_enforcement(tmp_path):
    # Block 'ls'
    res = run_cmd("ls -la", cwd=tmp_path, blacklist=["ls"])
    assert res.success is False
    assert "blacklisted" in res.error

def test_blacklist_path_bypass(tmp_path):
    # Block 'ls', try '/bin/ls'
    ls_path = shutil.which("ls")
    if not ls_path:
        pytest.skip("ls not found")
        
    res = run_cmd(f"{ls_path} -la", cwd=tmp_path, blacklist=["ls"])
    assert res.success is False
    assert "blacklisted" in res.error
```
