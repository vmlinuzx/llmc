"""
Rem's Ruthless Attack Tests.
"""

import sys
import tempfile
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from llmc.mcgrep import _run_search
from llmc.commands.repo_validator import validate_repo, check_bom_characters, ValidationResult

class MockOllamaHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/tags":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"models": [{"name": "llama3:latest"}]}')
        else:
            self.send_response(404)
            self.end_headers()

@pytest.fixture
def mock_ollama_server():
    server = HTTPServer(("localhost", 0), MockOllamaHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield f"http://localhost:{port}"
    server.shutdown()

class TestRuthlessMcgrep:
    
    def test_mcgrep_run_search_with_long_lines(self, capsys):
        """Test search with extremely long lines in snippet."""
        # Mock the tool_rag_search
        with patch("tools.rag_nav.tool_handlers.tool_rag_search") as mock_search:
            with patch("llmc.mcgrep.find_repo_root") as mock_root:
                mock_root.return_value = Path(".")
                
                mock_item = MagicMock()
                mock_item.file = "long.py"
                mock_item.snippet.location.path = "long.py"
                mock_item.snippet.location.start_line = 1
                mock_item.snippet.location.end_line = 1
                # 1MB string
                mock_item.snippet.text = "A" * 1024 * 1024
                
                mock_result = MagicMock()
                mock_result.source = "RAG_GRAPH"
                mock_result.freshness_state = "FRESH"
                mock_result.items = [mock_item]
                
                mock_search.return_value = mock_result
                
                _run_search("query", None, 1, False)
                
                captured = capsys.readouterr()
                assert "A" * 100 not in captured.out  # Should be truncated

    def test_mcgrep_invalid_result_structure(self, capsys):
        """Test search when result structure is unexpected."""
        with patch("tools.rag_nav.tool_handlers.tool_rag_search") as mock_search:
            with patch("llmc.mcgrep.find_repo_root") as mock_root:
                mock_root.return_value = Path(".")
                
                # Result missing 'items'
                mock_result = MagicMock()
                del mock_result.items 
                
                mock_search.return_value = mock_result
                
                # Should not crash
                _run_search("query", None, 1, False)
                captured = capsys.readouterr()
                assert "No results" in captured.out

class TestRuthlessValidator:
    
    def test_bom_detection_real_file(self, tmp_path):
        """Test BOM detection with a real file written with BOM."""
        bom_file = tmp_path / "bom.py"
        with open(bom_file, "wb") as f:
            f.write(b'\xef\xbb\xbfprint("hello")')
            
        result = ValidationResult(repo_path=tmp_path)
        check_bom_characters(tmp_path, result)
        
        assert any("BOM in" in i.message for i in result.issues)
        
    def test_bom_detection_access_denied(self, tmp_path):
        """Test BOM detection on file with no read permissions."""
        secret_file = tmp_path / "secret.py"
        secret_file.touch()
        secret_file.chmod(0o000)
        
        result = ValidationResult(repo_path=tmp_path)
        # Should not crash
        check_bom_characters(tmp_path, result)
        
        # Restore perms to delete
        secret_file.chmod(0o600)

    def test_validator_file_uri_handling(self, tmp_path):
        """Test if validator handles file:// URIs in config safely (or at least doesn't crash)."""
        config_file = tmp_path / "llmc.toml"
        
        # Point to a local file that definitely exists
        target_file = tmp_path / "target.json"
        target_file.write_text('{"models": []}')
        
        # Use file:// URI
        file_uri = target_file.as_uri()
        
        config_content = f"""
[enrichment]
[[enrichment.chain]]
provider = "ollama"
model = "test"
url = "{file_uri}"

[embeddings]
[embeddings.profiles.docs]
provider = "ollama"
model = "nomic-embed-text"
[embeddings.routes]
docs = {{ profile = "docs", index = "docs" }}
code = {{ profile = "docs", index = "code" }}
"""
        config_file.write_text(config_content)
        
        # Use run via validate_repo
        # We need check_connectivity=True
        result = validate_repo(tmp_path, check_connectivity=True, check_models=True)
        
        # It shouldn't crash. 
        # If it actually fetches the file, urllib might work or fail depending on implementation.
        # We just want to ensure it handles it gracefully.
        
        # Check issues for connectivity warnings/errors
        issues = [str(i) for i in result.issues if i.category == "connectivity"]
        # It likely failed because file:// response doesn't behave like HTTP response (no .status)
        # or because it's considered valid but data processing failed.
        
        # We don't assert pass/fail, just that it finished
        assert isinstance(result, ValidationResult)

    def test_validator_missing_optional_fields(self, tmp_path):
        """Test validator with a barebones valid config."""
        config_file = tmp_path / "llmc.toml"
        config_content = """
[enrichment]
[[enrichment.chain]]
provider = "openai"
model = "gpt-4"
# No URL needed for openai

[embeddings]
[embeddings.profiles.docs]
provider = "openai"
model = "text-embedding-3-small"
[embeddings.routes]
docs = { profile = "docs", index = "docs" }
code = { profile = "docs", index = "code" }
"""
        config_file.write_text(config_content)
        
        result = validate_repo(tmp_path)
        assert result.passed
        assert result.warning_count == 0  # Should be clean

