"""REST API application factory."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
import uuid

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from llmc_mcp.config import McpConfig
from llmc_mcp.transport.rest.middleware import RateLimitMiddleware
from llmc_mcp.transport.rest.routes import (
    get_file,
    get_health,
    get_symbol,
    get_symbol_lineage,
    get_symbol_references,
    get_workspaces,
    search,
)
from llmc_mcp.transport.rest.schemas import ErrorDetail, ErrorResponse
from llmc_mcp.transport.rest_auth import RestAuthMiddleware

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for unhandled errors.

    Logs the full traceback and returns a sanitized 500 response.
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    logger.error(
        f"Unhandled exception [request_id={request_id}]: {exc}",
        exc_info=True,
    )

    error = ErrorResponse(
        error=ErrorDetail(
            code="internal_error",
            message="An unexpected error occurred",
            details={"request_id": request_id},
        )
    )
    return JSONResponse(error.to_dict(), status_code=500)


def create_rest_api(config: McpConfig) -> Starlette:
    """
    Create REST API sub-application.

    Args:
        config: MCP configuration with rest_api and workspaces sections

    Returns:
        Starlette app configured with REST routes and middleware
    """
    # Build route list
    routes = [
        Route("/health", endpoint=get_health, methods=["GET"]),
        Route("/workspaces", endpoint=get_workspaces, methods=["GET"]),
        Route("/workspaces/{workspace_id}/search", endpoint=search, methods=["GET"]),
        Route("/workspaces/{workspace_id}/symbols/{name:path}", endpoint=get_symbol, methods=["GET"]),
        Route("/workspaces/{workspace_id}/symbols/{name:path}/references", endpoint=get_symbol_references, methods=["GET"]),
        Route("/workspaces/{workspace_id}/symbols/{name:path}/lineage", endpoint=get_symbol_lineage, methods=["GET"]),
        Route("/workspaces/{workspace_id}/files/{file_path:path}", endpoint=get_file, methods=["GET"]),
    ]

    # Create app with exception handler
    app = Starlette(
        routes=routes,
        exception_handlers={Exception: global_exception_handler},
        on_startup=[lambda: logger.info("REST API starting")],
        on_shutdown=[lambda: logger.info("REST API shutting down")],
    )

    # Store config in app state for access by route handlers
    app.state.config = config

    # Add middleware (order matters: last added = first executed)
    # 1. Rate limiting (innermost)
    app.add_middleware(
        RateLimitMiddleware,
        rpm=config.rest_api.rate_limit_rpm,
        burst=config.rest_api.rate_limit_burst,
        trust_proxy=config.rest_api.trust_proxy,
    )

    # 2. Authentication (outermost for REST)
    app.add_middleware(
        RestAuthMiddleware,
        auth_mode=config.rest_api.auth_mode,
        trust_proxy=config.rest_api.trust_proxy,
    )

    return app
