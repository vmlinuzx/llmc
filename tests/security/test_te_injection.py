import subprocess
import unittest
from unittest.mock import patch
from pathlib import Path
from llmc.te.cli import _handle_passthrough

class TestTEInjectionFixed(unittest.TestCase):
    def test_passthrough_shell_false(self):
        """
        SECURITY REGRESSION TEST
        Verifies that _handle_passthrough uses shell=False (list args), blocking injection.
        """
        with patch('subprocess.run') as mock_run:
            # Simulate 'te ls ; echo EXPLOITED'
            # te passes ['ls', ';', 'echo', 'EXPLOITED'] as args
            _handle_passthrough("ls", [";", "echo", "EXPLOITED"], Path("."), json_mode=False)
            
            # Check call args
            args, kwargs = mock_run.call_args
            command_executed = args[0]
            shell_arg = kwargs.get('shell')
            
            print(f"\n[Fixed] Command Executed: {command_executed}")
            print(f"[Fixed] shell=True? {shell_arg}")
            
            # Assertions for SECURITY
            self.assertFalse(shell_arg, "SECURITY: shell=True must be disabled!")
            self.assertIsInstance(command_executed, list, "SECURITY: Command must be a list of args!")
            self.assertEqual(command_executed, ["ls", ";", "echo", "EXPLOITED"], "SECURITY: Args must be separate list items!")

if __name__ == '__main__':
    unittest.main()