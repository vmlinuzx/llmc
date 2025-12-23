import sys
import pytest
from unittest.mock import patch
from typer.testing import CliRunner
from llmc.main import app

runner = CliRunner()

@pytest.fixture(autouse=True)
def restore_argv():
    """Restore sys.argv after each test."""
    original_argv = sys.argv[:]
    yield
    sys.argv = original_argv

def test_chat_shell_injection():
    """Verify that shell injection characters are sanitized."""
    malicious_prompt = "; ls -la"
    
    with patch("llmc_agent.cli.main") as mock_agent_main:
        # Capture sys.argv at the time agent_main is called
        captured_argv = []
        def side_effect(*args, **kwargs):
            captured_argv.extend(sys.argv)
        mock_agent_main.side_effect = side_effect
        
        result = runner.invoke(app, ["chat", malicious_prompt])
        
        assert result.exit_code == 0
        mock_agent_main.assert_called_once()
        
        # Verify sanitization
        # sys.argv[0] is "llmc-chat", sys.argv[1] is the prompt
        assert len(captured_argv) >= 2
        prompt_passed = captured_argv[1]
        
        # Assert that the prompt passed is NOT the exact malicious string
        # This confirms some form of sanitization or escaping occurred
        assert prompt_passed != malicious_prompt, "Shell injection prompt was not sanitized"

def test_chat_xss_injection():
    """Verify that XSS payloads are sanitized."""
    malicious_prompt = "<script>alert('XSS')</script>"
    
    with patch("llmc_agent.cli.main") as mock_agent_main:
        captured_argv = []
        def side_effect(*args, **kwargs):
            captured_argv.extend(sys.argv)
        mock_agent_main.side_effect = side_effect
        
        result = runner.invoke(app, ["chat", malicious_prompt])
        
        assert result.exit_code == 0
        mock_agent_main.assert_called_once()
        
        assert len(captured_argv) >= 2
        prompt_passed = captured_argv[1]
        
        assert prompt_passed != malicious_prompt, "XSS prompt was not sanitized"

def test_chat_sql_injection():
    """Verify that SQL injection payloads are sanitized."""
    malicious_prompt = "' OR 1=1 --"
    
    with patch("llmc_agent.cli.main") as mock_agent_main:
        captured_argv = []
        def side_effect(*args, **kwargs):
            captured_argv.extend(sys.argv)
        mock_agent_main.side_effect = side_effect
        
        result = runner.invoke(app, ["chat", malicious_prompt])
        
        assert result.exit_code == 0
        mock_agent_main.assert_called_once()
        
        assert len(captured_argv) >= 2
        prompt_passed = captured_argv[1]
        
        assert prompt_passed != malicious_prompt, "SQL injection prompt was not sanitized"
