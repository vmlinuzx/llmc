import unittest
import asyncio
from unittest.mock import patch, MagicMock
from llmc_mcp.server import LlmcMcpServer

class TestMCPShellFixed(unittest.IsolatedAsyncioTestCase):
    async def test_executable_handler_shell_false(self):
        """
        SECURITY REGRESSION TEST
        Verifies that MCP server uses shell=False.
        """
        # Mock config
        mock_config = MagicMock()
        mock_config.tools.allowed_roots = ['.']
        mock_config.tools.exec_timeout = 5
        mock_config.code_execution.enabled = False 
        mock_config.tools.executables = {} 
        mock_config.observability = MagicMock() 

        # We need to mock Server because __init__ creates one
        with patch('llmc_mcp.server.Server') as MockServer:
            server_instance = LlmcMcpServer(mock_config)
        
        with patch('subprocess.run') as mock_run:
            # Call handler
            await server_instance._handle_run_executable('/bin/echo', ['hello'])
            
            args, kwargs = mock_run.call_args
            command = args[0]
            shell_used = kwargs.get('shell')
            
            print(f"\n[Fixed] MCP Command: {command}")
            print(f"[Fixed] MCP shell=True? {shell_used}")
            
            self.assertFalse(shell_used, "SECURITY: MCP server must NOT use shell=True")
            self.assertEqual(command, ['/bin/echo', 'hello'], "SECURITY: Command must be a list")

if __name__ == '__main__':
    unittest.main()

