# SDD: Security Isolation Logging

## 1. Gap Description
The `llmc_mcp/isolation.py` module allows bypassing isolation checks via `LLMC_ISOLATED=1` environment variable.
However, it does not appear to log this critical security bypass to a persistent audit log or stderr in a conspicuous way during `require_isolation` check (only debug/trace might catch it if configured).
If a user accidentally runs in this mode, they are vulnerable.
We need to ensure that when `require_isolation` passes due to override, a warning is logged.

## 2. Target Location
`tests/security/test_isolation_logging.py`

## 3. Test Strategy
1. **Mock Logging**: Patch `logging.getLogger` or `llmc_mcp.isolation.logger`.
2. **Trigger Bypass**: Set `LLMC_ISOLATED=1` and call `require_isolation`.
3. **Assert Log**: Verify that a WARNING or CRITICAL log message is emitted indicating "Security Isolation Bypassed".

## 4. Implementation Details
```python
import os
import unittest
from unittest.mock import patch, MagicMock
from llmc_mcp.isolation import require_isolation, is_isolated_environment

class TestIsolationLogging(unittest.TestCase):
    def setUp(self):
        is_isolated_environment.cache_clear()

    def tearDown(self):
        is_isolated_environment.cache_clear()

    @patch("llmc_mcp.isolation.logger")
    def test_bypass_logging(self, mock_logger):
        """Verify that bypassing isolation logs a warning."""
        with patch.dict(os.environ, {"LLMC_ISOLATED": "1"}):
            # We expect is_isolated_environment to return True
            # And require_isolation to pass.
            # But we ALSO want to ensure it logged a warning.

            # Note: Current implementation does NOT log.
            # So this test is expected to FAIL until fixed.

            try:
                require_isolation("test_tool")
            except RuntimeError:
                self.fail("require_isolation raised RuntimeError despite LLMC_ISOLATED=1")

            # Check for warning
            # We look for any warning call
            warnings = [call for call in mock_logger.warning.call_args_list]
            if not warnings:
                # Also check critical or error
                warnings = [call for call in mock_logger.critical.call_args_list]

            self.assertTrue(len(warnings) > 0, "Should log a warning when isolation is bypassed via env var")
```
