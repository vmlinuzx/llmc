import os
import pytest
from llmc_mcp.tools.cmd import run_cmd

@pytest.fixture
def isolated_env():
    old_env = os.environ.get("LLMC_ISOLATED")
    os.environ["LLMC_ISOLATED"] = "1"
    yield
    if old_env is None:
        del os.environ["LLMC_ISOLATED"]
    else:
        os.environ["LLMC_ISOLATED"] = old_env

@pytest.mark.allow_sleep
def test_command_injection_prevention_file_creation(isolated_env, tmp_path):
    """
    Verify that chained commands do not execute.
    We attempt to create a file using a chained 'touch' command.
    """
    vuln_file = tmp_path / "vuln.txt"
    # Ensure it doesn't exist
    if vuln_file.exists():
        vuln_file.unlink()
        
    # Attempt injection: echo something; touch file
    cmd = f"echo safe; touch {str(vuln_file)}"
    
    result = run_cmd(cmd, cwd=tmp_path)
    
    # Verification
    # 1. The marker file must NOT exist
    assert not vuln_file.exists(), "Security check failed: Chained command executed and created a file!"
    
    # 2. The output should contain the literal command part if it was treated as an argument
    # /bin/echo usually prints its arguments.
    # So it should print "safe; touch /path/to/vuln.txt"
    # Note: shlex.split might strip quotes around 'safe' if I used them, but here I didn't use quotes in the f-string variable `cmd`.
    # wait, cmd = "echo safe; touch ..."
    # shlex.split -> ['echo', 'safe;', 'touch', '...'] (if ; is not a separator)
    # Actually shlex.split("echo a; b") -> ['echo', 'a', ';', 'b'] in posix mode?
    # Let's verify shlex behavior in thought.
    
    # If shlex splits it into multiple args including ';', then /bin/echo will print them all.
    assert "touch" in result.stdout

@pytest.mark.allow_sleep
def test_valid_command_execution(isolated_env, tmp_path):
    """Verify that standard valid commands still work."""
    cmd = "ls -la"
    result = run_cmd(cmd, cwd=tmp_path)
    assert result.success
    assert result.exit_code == 0
    # ls output usually contains '.' and '..'
    assert "." in result.stdout
