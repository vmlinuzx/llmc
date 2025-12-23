
import pytest
from llmc_mcp.tools import code_exec

def test_run_untrusted_python_security_warning():
    """Verify that the tool's docstring includes a prominent security warning."""
    assert "WARNING" in code_exec.run_untrusted_python.__doc__
    assert "sandbox" in code_exec.run_untrusted_python.__doc__
    assert "CRITICAL" in code_exec.run_untrusted_python.__doc__

def test_module_docstring_security_warning():
    """Verify that the module docstring also contains a security warning."""
    assert "SECURITY" in code_exec.__doc__
    assert "sandbox" in code_exec.__doc__
    assert "vulnerability" in code_exec.__doc__

def test_tool_is_renamed():
    """Verify that the tool has been renamed from execute_code."""
    assert hasattr(code_exec, "run_untrusted_python")
    assert not hasattr(code_exec, "execute_code")
