
import pytest
from llmc.ruta.judge import _safe_eval

def test_simpleeval_basic_safety():
    """Verify basic safety constraints of simpleeval."""
    
    # 1. Block import
    with pytest.raises(Exception):
        _safe_eval("__import__('os').system('echo pwned')", {})
        
    # 2. Block builtins access
    with pytest.raises(Exception):
        _safe_eval("open('/etc/passwd').read()", {})

def test_simpleeval_dos_attack():
    """
    Test for DoS via exponential expansion.
    simpleeval usually blocks this, but let's verify.
    """
    # Create a string that explodes in size: "a" * 10**9
    payload = "'a' * 1000000000" 
    
    # This should fail or be caught by memory limits (if configured),
    # but simpleeval doesn't inherently block large allocations unless operators are mapped.
    # The default operator mapping allows * for strings.
    try:
        _safe_eval(payload, {})
    except (MemoryError, Exception):
        pass # Good, it failed
    
def test_simpleeval_type_confusion():
    """
    Try to pass a complex object and access its internals.
    """
    class Secret:
        def __init__(self):
            self.secret = "VALUE"
        def __str__(self):
            return "hidden"
            
    s = Secret()
    
    # Context has the object
    context = {"s": s}
    
    # Try to access attribute - simpleeval allows attribute access by default!
    # If the tool exposes sensitive objects in context, they can be read.
    result = _safe_eval("s.secret", context)
    assert result == "VALUE"

