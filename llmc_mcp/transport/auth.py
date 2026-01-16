"""API key authentication middleware for HTTP transport."""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from llmc_mcp.transport.utils import load_api_key

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    API key validation middleware for MCP HTTP transport.

    Validates X-API-Key header or api_key query parameter against
    a stored key. The /health endpoint is public (no auth required).
    
    NOTE: Paths starting with /api/v1 are skipped - they are handled
    by the REST API's own RestAuthMiddleware with loopback bypass.

    API key is loaded from (in order):
    1. Explicit api_key parameter
    2. LLMC_MCP_API_KEY environment variable
    3. ~/.llmc/mcp-api-key file
    4. Auto-generated and saved to ~/.llmc/mcp-api-key
    """

    def __init__(self, app, api_key: str | None = None):
        """
        Initialize auth middleware.

        Args:
            app: ASGI app to wrap
            api_key: Explicit API key (optional, will load from env/file)
        """
        super().__init__(app)

        self.api_key = api_key or load_api_key()
        logger.info("API key authentication enabled")

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Validate API key before forwarding request.

        Args:
            request: The incoming request
            call_next: Next middleware/endpoint

        Returns:
            Response (401 if auth fails, otherwise from call_next)
        """
        # Public endpoints - no auth required
        if request.url.path == "/health":
            return await call_next(request)
        
        # REST API paths - handled by RestAuthMiddleware with loopback bypass
        if request.url.path.startswith("/api/v1"):
            return await call_next(request)

        provided_key = request.headers.get("X-API-Key") or request.query_params.get(
            "api_key"
        )

        if not provided_key:
            return JSONResponse(
                {"error": "Missing API key (X-API-Key header or api_key query param)"},
                status_code=401,
            )

        if not secrets.compare_digest(provided_key, self.api_key):
            return JSONResponse(
                {"error": "Invalid API key"},
                status_code=401,
            )

        return await call_next(request)
