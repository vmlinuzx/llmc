from unittest.mock import patch

import pytest

from llmc_mcp.tools.code_exec import execute_code


def test_dos_via_exit():
    """
    Test that calling execute_code with sys.exit() propagates SystemExit
    when isolation is bypassed (mocked).
    """
    # Patch require_isolation to bypass the environment check
    with patch("llmc_mcp.isolation.require_isolation") as mock_iso:
        # Code that triggers sys.exit(1)
        code = "import sys; sys.exit(1)"

        # We expect SystemExit to be raised because the current implementation
        # catches Exception but not BaseException (which SystemExit inherits from).
        with pytest.raises(SystemExit):
            execute_code(code, lambda name, args: None)


def test_dos_via_keyboard_interrupt():
    """
    Test that calling execute_code with raise KeyboardInterrupt propagates KeyboardInterrupt.
    """
    # Patch require_isolation to bypass the environment check
    with patch("llmc_mcp.isolation.require_isolation") as mock_iso:
        # Code that raises KeyboardInterrupt
        code = "raise KeyboardInterrupt"

        # We expect KeyboardInterrupt to be raised.
        with pytest.raises(KeyboardInterrupt):
            execute_code(code, lambda name, args: None)


if __name__ == "__main__":
    pytest.main([__file__])
