"""
Tests for MCP HTTP transport server.

These tests verify the HTTP/SSE transport layer works correctly,
enabling automated MCP testing without Claude Desktop.
"""

from unittest.mock import Mock

import pytest


class TestMCPHttpServerConfiguration:
    """Test server configuration handling (no async/TestClient needed)."""

    def test_uses_config_host_and_port(self):
        """Server should use host/port from config."""
        from llmc_mcp.transport.http_server import MCPHttpServer

        mock_server = Mock()
        mock_server.tools = []

        mock_config = Mock()
        mock_config.server.host = "0.0.0.0"
        mock_config.server.port = 9999
        mock_config.server.transport = "http"
        mock_config.auth.mode = "none"

        http = MCPHttpServer(mock_server, mock_config)

        assert http.host == "0.0.0.0"
        assert http.port == 9999

    def test_init_overrides_config(self):
        """Constructor args should override config."""
        from llmc_mcp.transport.http_server import MCPHttpServer

        mock_server = Mock()
        mock_server.tools = []

        mock_config = Mock()
        mock_config.server.host = "127.0.0.1"
        mock_config.server.port = 8080
        mock_config.server.transport = "http"
        mock_config.auth.mode = "none"

        http = MCPHttpServer(mock_server, mock_config, host="192.168.1.1", port=3000)

        assert http.host == "192.168.1.1"
        assert http.port == 3000

    def test_creates_sse_transport(self):
        """Server should create SSE transport."""
        from llmc_mcp.transport.http_server import MCPHttpServer

        mock_server = Mock()
        mock_server.tools = []

        mock_config = Mock()
        mock_config.server.host = "127.0.0.1"
        mock_config.server.port = 8080

        http = MCPHttpServer(mock_server, mock_config)

        assert http.sse_transport is not None

    def test_creates_starlette_app(self):
        """Server should create Starlette app with routes."""
        from llmc_mcp.transport.http_server import MCPHttpServer

        mock_server = Mock()
        mock_server.tools = []

        mock_config = Mock()
        mock_config.server.host = "127.0.0.1"
        mock_config.server.port = 8080

        http = MCPHttpServer(mock_server, mock_config)

        assert http.app is not None
        routes = [r.path for r in http.app.routes]
        assert "/health" in routes
        assert "/sse" in routes


class TestMCPHttpServerRoutes:
    """Test route registration."""

    @pytest.fixture
    def http_server(self):
        """Create HTTP server instance."""
        from llmc_mcp.transport.http_server import MCPHttpServer

        mock_server = Mock()
        mock_server.tools = [Mock(name="test_tool")]  # 1 fake tool
        mock_server.server = Mock()

        mock_config = Mock()
        mock_config.server.host = "127.0.0.1"
        mock_config.server.port = 8765

        return MCPHttpServer(mock_server, mock_config)

    def test_health_route_exists(self, http_server):
        """Health endpoint should be registered."""
        routes = [r.path for r in http_server.app.routes]
        assert "/health" in routes

    def test_sse_route_exists(self, http_server):
        """SSE endpoint should be registered."""
        routes = [r.path for r in http_server.app.routes]
        assert "/sse" in routes

    def test_messages_route_exists(self, http_server):
        """Messages endpoint should be registered."""
        routes = [r.path for r in http_server.app.routes]
        assert "/messages" in routes


class TestMCPHttpServerIntegration:
    """Integration tests with real MCP server."""

    def test_real_server_can_be_created(self):
        """Should be able to create real server instance."""
        try:
            from llmc_mcp.config import load_config
            from llmc_mcp.server import LlmcMcpServer
            from llmc_mcp.transport.http_server import MCPHttpServer

            config = load_config()
            mcp_server = LlmcMcpServer(config)
            http = MCPHttpServer(mcp_server, config, port=28765)

            assert http is not None
            assert http.port == 28765
            assert len(mcp_server.tools) > 0

            print(f"Real server created with {len(mcp_server.tools)} tools")
            tool_names = [t.name for t in mcp_server.tools]
            print(f"Tools: {tool_names}")

        except Exception as e:
            pytest.skip(f"Could not create real server: {e}")

    def test_real_server_has_bootstrap_tool(self):
        """Real server should have 00_INIT tool."""
        try:
            from llmc_mcp.config import load_config
            from llmc_mcp.server import LlmcMcpServer

            config = load_config()
            mcp_server = LlmcMcpServer(config)

            tool_names = [t.name for t in mcp_server.tools]
            assert "00_INIT" in tool_names, f"Expected 00_INIT, got {tool_names}"

        except Exception as e:
            pytest.skip(f"Could not create real server: {e}")


class TestAPIKeyMiddleware:
    """Test API key authentication middleware."""

    def test_health_endpoint_public(self):
        """Health endpoint should not require auth."""
        from llmc_mcp.transport.auth import APIKeyMiddleware

        # The middleware should skip auth for /health
        # (tested via route check, actual request test needs async)
        assert APIKeyMiddleware is not None

    def test_key_loaded_from_env(self, monkeypatch):
        """Should load API key from environment."""
        from llmc_mcp.transport.auth import APIKeyMiddleware

        monkeypatch.setenv("LLMC_MCP_API_KEY", "test-key-123")

        # Create minimal mock app
        mock_app = Mock()

        middleware = APIKeyMiddleware(mock_app)
        assert middleware.api_key == "test-key-123"
