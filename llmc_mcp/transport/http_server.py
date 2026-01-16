"""HTTP server with SSE transport for MCP daemon mode."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from llmc_mcp.transport.auth import APIKeyMiddleware
from llmc_mcp.transport.rest.app import create_rest_api

try:
    from mcp.server.sse import SseServerTransport
except ImportError as e:
    raise ImportError(
        "CRITICAL: Missing 'mcp' dependency. "
        "The 'mcp' package is required. "
        "Application must be run in .venv environment for dependency."
    ) from e

from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

if TYPE_CHECKING:
    from starlette.requests import Request

    from llmc_mcp.config import McpConfig
    from llmc_mcp.server import LlmcMcpServer

logger = logging.getLogger(__name__)


class MCPHttpServer:
    """
    HTTP server that exposes MCP over SSE transport.

    This enables external systems to connect to LLMC's MCP server
    over HTTP instead of stdio. Uses Server-Sent Events (SSE) for
    bidirectional communication.

    Example:
        server = MCPHttpServer(mcp_server, host="127.0.0.1", port=8765)
        server.run()  # Blocks, serving HTTP/SSE
    """

    def __init__(
        self,
        mcp_server: LlmcMcpServer,
        config: McpConfig,
        host: str | None = None,
        port: int | None = None,
    ):
        """
        Initialize HTTP server.

        Args:
            mcp_server: The LLMC MCP server instance to expose
            config: MCP configuration
            host: Bind address (default from config)
            port: Port number (default from config)
        """
        self.mcp_server = mcp_server
        self.config = config
        self.host = host or config.server.host
        self.port = port or config.server.port

        # Create SSE transport
        self.sse_transport = SseServerTransport("/messages")

        # Build Starlette app
        self.app = self._create_app()

        logger.info(f"HTTP server initialized (will bind to {self.host}:{self.port})")

    def _create_app(self) -> Starlette:
        """Create the Starlette ASGI application."""
        routes = []

        if self.config.rest_api.enabled:
            rest_app = create_rest_api(self.config)
            routes.append(Mount("/api/v1", app=rest_app))
            logger.info("REST API mounted at /api/v1")

        routes.extend(
            [
                Route("/health", endpoint=self._health, methods=["GET"]),
                Route("/sse", endpoint=self._handle_sse, methods=["GET"]),
                Mount("/messages", app=self.sse_transport.handle_post_message),
            ]
        )

        app = Starlette(
            routes=routes,
            on_startup=[self._on_startup],
            on_shutdown=[self._on_shutdown],
        )

        # Add auth middleware
        app.add_middleware(APIKeyMiddleware)

        return app

    async def _on_startup(self) -> None:
        """Startup hook."""
        logger.info("HTTP server starting up")

    async def _on_shutdown(self) -> None:
        """Shutdown hook."""
        logger.info("HTTP server shutting down")

    async def _health(self, request: Request) -> JSONResponse:
        """
        Health check endpoint (public, no auth).

        Returns:
            {"status": "ok", "tools": <count>, "transport": "http"}
        """
        return JSONResponse(
            {
                "status": "ok",
                "tools": len(self.mcp_server.tools),
                "transport": "http",
                "server": "llmc-mcp",
            }
        )

    async def _handle_sse(self, request: Request) -> Response:
        """
        Handle SSE connection - this is where MCP protocol runs.

        This endpoint establishes a bidirectional SSE connection and
        runs the MCP server protocol over it.
        """
        logger.info(f"SSE connection from {request.client}")

        async with self.sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            read_stream, write_stream = streams
            await self.mcp_server.server.run(
                read_stream,
                write_stream,
                self.mcp_server.server.create_initialization_options(),
            )

        logger.info(f"SSE connection closed from {request.client}")
        return Response()

    def run(self, host: str | None = None, port: int | None = None) -> None:
        """
        Run the HTTP server (blocks).

        Args:
            host: Override bind address
            port: Override port number
        """
        import uvicorn

        bind_host = host or self.host
        bind_port = port or self.port

        logger.info(f"Starting HTTP server on {bind_host}:{bind_port}")

        uvicorn.run(
            self.app,
            host=bind_host,
            port=bind_port,
            log_level="info",
        )
