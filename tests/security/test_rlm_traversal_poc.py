
from pathlib import Path

import pytest

from llmc.rlm.session import RLMSession


def test_rlm_load_context_path_traversal():
    """
    POC: RLMSession.load_context allows reading arbitrary files if passed a Path object.
    """
    session = RLMSession()
    
    # Attempt to read /etc/passwd (or any sensitive file)
    # We'll use a relative path to something outside our repo if possible, 
    # but /etc/passwd is a classic POC.
    target = Path("/etc/passwd")
    
    if not target.exists():
        pytest.skip("/etc/passwd not found, skipping POC")
        
    # This SHOULD fail if there was path validation
    session.load_context(target)
    
    # If we reached here, it means we loaded the file into the session context
    assert "root:" in session.sandbox._namespace.get("context", "")
    print("\n[!] VULNERABILITY CONFIRMED: RLMSession.load_context loaded /etc/passwd")

def test_rlm_load_code_context_path_traversal():
    """
    POC: RLMSession.load_code_context allows reading arbitrary files if passed a Path object.
    """
    session = RLMSession()
    target = Path("/etc/passwd")
    
    if not target.exists():
        pytest.skip("/etc/passwd not found, skipping POC")
        
    # This SHOULD fail
    session.load_code_context(target)
    
    # Check if content was loaded
    # Note: load_code_context might fail later due to TreeSitter parsing non-code, 
    # but the read_text() happens BEFORE that.
    assert "root:" in session.sandbox._namespace.get("context", "")
    print("\n[!] VULNERABILITY CONFIRMED: RLMSession.load_code_context loaded /etc/passwd")

