import pytest
from llmc.ruta.judge import _safe_eval

def test_safe_eval_basic_arithmetic():
    """Verify that basic arithmetic still works."""
    assert _safe_eval("1 + 1", {}) == 2
    assert _safe_eval("10 > 5", {}) is True
    assert _safe_eval("len([1, 2, 3])", {"len": len}) == 3

def test_safe_eval_blocks_import():
    """Verify that __import__ is blocked."""
    with pytest.raises(Exception): # simpleeval raises NameError or specific errors
        _safe_eval("__import__('os').system('ls')", {})

def test_safe_eval_blocks_open():
    """Verify that open is blocked."""
    with pytest.raises(Exception):
        _safe_eval("open('/etc/passwd')", {})

def test_safe_eval_blocks_subclass_gadgets():
    """Verify that common python jailbreak gadgets are blocked."""
    gadget = "(1).__class__.__base__.__subclasses__()"
    with pytest.raises(Exception):
        _safe_eval(gadget, {})

def test_safe_eval_context_isolation():
    """Verify that context is respected and isolated."""
    context = {"x": 10, "y": 20}
    assert _safe_eval("x + y", context) == 30
    with pytest.raises(Exception):
        _safe_eval("z", context)
