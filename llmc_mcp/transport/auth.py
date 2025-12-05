"""API key authentication middleware for HTTP transport."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import secrets
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    API key validation middleware for MCP HTTP transport.

    Validates X-API-Key header or api_key query parameter against
    a stored key. The /health endpoint is public (no auth required).

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

        # Load or generate API key
        self.api_key = api_key or self._load_or_generate_key()
        logger.info("API key authentication enabled")

    def _load_or_generate_key(self) -> str:
        """
        Load API key from env/file, or generate and save a new one.

        Returns:
            The API key string
        """
        # Try environment variable
        env_key = os.getenv("LLMC_MCP_API_KEY")
        if env_key:
            logger.info("API key loaded from LLMC_MCP_API_KEY")
            return env_key

        # Try file
        key_path = Path.home() / ".llmc" / "mcp-api-key"
        if key_path.exists():
            try:
                key = key_path.read_text().strip()
                logger.info(f"API key loaded from {key_path}")
                return key
            except Exception as e:
                logger.warning(f"Failed to load API key from {key_path}: {e}")

        # Generate new key
        key = self._generate_and_save_key(key_path)
        logger.info(f"Generated new API key and saved to {key_path}")
        return key

    def _generate_and_save_key(self, key_path: Path) -> str:
        """
        Generate a new API key and save it.

        Args:
            key_path: Path to save the key

        Returns:
            The generated API key
        """
        # Generate secure random key
        key = secrets.token_urlsafe(32)

        # Save to file with restrictive permissions
        try:
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_text(key)
            key_path.chmod(0o600)  # rw-------
            logger.info(f"Saved API key to {key_path} (mode 0600)")
        except Exception as e:
            logger.error(f"Failed to save API key to {key_path}: {e}")
            logger.warning("API key is ephemeral - will change on restart!")

        return key

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Validate API key before forwarding request.

        Args:
            request: The incoming request
            call_next: Next middleware/endpoint

        Returns:
            Response (401 if auth fails, otherwise from call_next)
        """
        # Health endpoint is public
        if request.url.path == "/health":
            return await call_next(request)

        # Check for API key in header or query param
        provided_key = request.headers.get("X-API-Key") or request.query_params.get(
            "api_key"
        )

        # Validate
        if not provided_key:
            return JSONResponse(
                {"error": "Missing API key (X-API-Key header or api_key query param)"},
                status_code=401,
            )

        # Constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(provided_key, self.api_key):
            return JSONResponse(
                {"error": "Invalid API key"},
                status_code=401,
            )

        # Authenticated - proceed
        return await call_next(request)
