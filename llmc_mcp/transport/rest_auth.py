"""REST API authentication middleware with loopback bypass."""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from llmc_mcp.transport.utils import get_client_ip, is_loopback, load_api_key

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

logger = logging.getLogger(__name__)


class RestAuthMiddleware(BaseHTTPMiddleware):
    """
    REST API authentication with loopback bypass.

    Behavior based on auth_mode:
    - "auto": Skip auth for loopback (127.0.0.1, ::1), require for remote
    - "token": Always require X-API-Key header
    - "none": No authentication (NOT RECOMMENDED)
    """

    def __init__(
        self,
        app,
        auth_mode: str = "auto",
        trust_proxy: bool = False,
    ):
        """
        Initialize REST auth middleware.

        Args:
            app: ASGI app to wrap
            auth_mode: Authentication mode ("auto", "token", "none")
            trust_proxy: Trust X-Forwarded-For header for client IP
        """
        super().__init__(app)
        self.auth_mode = auth_mode
        self.trust_proxy = trust_proxy
        self.api_key = load_api_key()
        logger.info(f"REST auth middleware enabled (mode={auth_mode})")

    async def dispatch(self, request: Request, call_next) -> Response:
        """Validate authentication before forwarding request."""
        if request.url.path.endswith("/health"):
            return await call_next(request)

        if self.auth_mode == "none":
            return await call_next(request)

        client_ip = get_client_ip(request, self.trust_proxy)

        if self.auth_mode == "auto" and is_loopback(client_ip):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return JSONResponse(
                {
                    "error": {
                        "code": "unauthorized",
                        "message": "Missing API key (X-API-Key header required)",
                    }
                },
                status_code=401,
            )

        if not secrets.compare_digest(api_key, self.api_key):
            return JSONResponse(
                {
                    "error": {
                        "code": "unauthorized",
                        "message": "Invalid API key",
                    }
                },
                status_code=401,
            )

        return await call_next(request)
