
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Import the tool
try:
    from llmc_mcp.tools.cmd import run_cmd
except ImportError:
    import sys
    sys.path.append(os.getcwd())
    from llmc_mcp.tools.cmd import run_cmd

def test_run_cmd_allows_anything_if_isolated(tmp_path):
    """
    Verify that run_cmd allows ANY command if isolation check passes,
    because the default blacklist is empty.
    """
    
    # 1. Mock require_isolation to pass
    with patch("llmc_mcp.isolation.require_isolation") as mock_iso:
        mock_iso.return_value = None  # No error raised
        
        # 2. Try to run a command that definitely shouldn't be allowed in a "safe" tool
        # e.g. 'python -c ...' or just 'sh'
        # We'll use 'echo' but with a "dangerous" looking intent that a blacklist SHOULD catch
        # if it were robust. But here we just want to prove the blacklist is empty.
        
        # We can also check the DEFAULT_BLACKLIST directly
        from llmc_mcp.tools.cmd import DEFAULT_BLACKLIST
        print(f"\n[!] DEFAULT_BLACKLIST size: {len(DEFAULT_BLACKLIST)}")
        
        if len(DEFAULT_BLACKLIST) == 0:
            print("[+] CONFIRMED: Default blacklist is empty.")
        
        # 3. Execute
        # We use a simple command to avoid actual damage, but the point is it runs.
        result = run_cmd("echo 'I am running'", cwd=tmp_path)
        
        if result.success:
            print("[+] Command executed successfully.")
        else:
            print(f"[-] Command failed: {result.error}")
            
        assert result.success
        assert "I am running" in result.stdout

        # 4. Try command chaining (should fail due to shell=False, verify this!)
        # This is checking the fix for the previous vulnerability
        result_chain = run_cmd("echo A; echo B", cwd=tmp_path)
        
        # Since shell=False, "echo A; echo B" should be interpreted as:
        # Binary: "echo"
        # Arg1: "A;"
        # Arg2: "echo"
        # Arg3: "B"
        # So it should print "A; echo B" literal, OR fail if 'echo' treats them weirdly.
        # It should NOT execute 'echo B' as a separate command.
        
        print(f"Chain Result Stdout: {result_chain.stdout.strip()}")
        
        if "; echo B" in result_chain.stdout or "A; echo B" in result_chain.stdout:
             print("[+] Verified: Command chaining is prevented by shell=False.")
        elif "B" == result_chain.stdout.strip(): # If it just printed B, chaining worked!
             print("[-] VULNERABILITY: Command chaining worked!")
             pytest.fail("Command chaining possible!")
        
        # 5. Argument Injection?
        # Since shell=False, we can't inject operators.
        # But if we can run 'python', we can do anything.
        result_py = run_cmd('python3 -c "print(1+1)"', cwd=tmp_path)
        if result_py.success and "2" in result_py.stdout:
             print("[+] Verified: We can run arbitrary code via interpreters (python/perl/etc) because they are not blacklisted.")
             pytest.fail("CRITICAL: Empty blacklist allows executing interpreters (python, etc).")

if __name__ == "__main__":
    test_run_cmd_allows_anything_if_isolated(Path("."))
