"""Test process-based sandbox."""

import pytest
from llmc.rlm.sandbox.process_backend import ProcessSandboxBackend


class TestProcessSandbox:
    def test_timeout_kills_process(self):
        """V1.1.1: Verify process is actually killed on timeout."""
        sandbox = ProcessSandboxBackend(timeout_seconds=1)
        sandbox.start()
        
        # This would hang forever with threads
        result = sandbox.execute("while True: pass")
        
        assert not result.success
        assert "timeout" in result.error.lower() or "killed" in result.error.lower()
        sandbox.stop()
    
    def test_state_persists_via_namespace_updates(self):
        """Variables survive across executions."""
        sandbox = ProcessSandboxBackend()
        sandbox.start()
        
        sandbox.execute("x = 42")
        result = sandbox.execute("print(x * 2)")
        
        assert result.success
        assert "84" in result.stdout
        sandbox.stop()
    
    def test_blocked_imports(self):
        """Dangerous imports are blocked."""
        sandbox = ProcessSandboxBackend(security_mode="restrictive")
        sandbox.start()
        
        result = sandbox.execute("import os")
        
        assert not result.success
        assert "blocked" in result.error.lower() or "Import" in result.error
        sandbox.stop()
    
    def test_final_answer_via_function(self):
        """FINAL() function works."""
        sandbox = ProcessSandboxBackend()
        sandbox.start()
        
        result = sandbox.execute('FINAL("test answer")')
        
        assert result.success
        assert result.final_answer == "test answer"
        sandbox.stop()
    
    def test_final_answer_via_variable(self):
        """FINAL_VAR works."""
        sandbox = ProcessSandboxBackend()
        sandbox.start()
        
        result = sandbox.execute('FINAL_VAR = "var answer"')
        
        assert result.success
        assert result.final_answer == "var answer"
        sandbox.stop()
    
    def test_allowed_imports(self):
        """Whitelisted imports work."""
        sandbox = ProcessSandboxBackend()
        sandbox.start()
        
        result = sandbox.execute("import json; print(json.dumps({'a': 1}))")
        
        assert result.success
        assert '{"a": 1}' in result.stdout
        sandbox.stop()
