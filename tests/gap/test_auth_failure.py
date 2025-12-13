import pytest
import httpx
from pathlib import Path
import os

# Configuration
BASE_URL = "http://localhost:8765"
KEY_FILE = Path.home() / ".llmc" / "mcp-api-key"

def get_api_key():
    if not KEY_FILE.exists():
        return None
    return KEY_FILE.read_text().strip()

def is_server_running():
    try:
        httpx.get(f"{BASE_URL}/health", timeout=1.0)
        return True
    except httpx.ConnectError:
        return False

@pytest.mark.allow_network
@pytest.mark.skipif(not is_server_running(), reason="MCP server not running on port 8765")
class TestAuthFailure:
    
    def test_health_public_access(self):
        """Test that /health is accessible without authentication."""
        response = httpx.get(f"{BASE_URL}/health")
        assert response.status_code == 200, "Health endpoint should be public"

    def test_missing_api_key(self):
        """Test that protected endpoints reject requests without API key."""
        response = httpx.get(f"{BASE_URL}/sse")
        assert response.status_code == 401, "Should return 401 when API key is missing"

    def test_invalid_api_key(self):
        """Test that protected endpoints reject requests with invalid API key."""
        headers = {"X-API-Key": "invalid-key-123"}
        response = httpx.get(f"{BASE_URL}/sse", headers=headers)
        assert response.status_code == 401, "Should return 401 when API key is invalid"

    def test_valid_api_key(self):
        """Test that protected endpoints accept requests with valid API key."""
        api_key = get_api_key()
        if not api_key:
            pytest.skip("MCP API key not found in ~/.llmc/mcp-api-key")
            
        headers = {"X-API-Key": api_key}
        # Use stream=True to avoid reading the infinite SSE stream
        with httpx.stream("GET", f"{BASE_URL}/sse", headers=headers) as response:
            assert response.status_code == 200, "Should return 200 with valid API key"
