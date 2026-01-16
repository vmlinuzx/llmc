"""Shared utilities for HTTP transport layer."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.requests import Request

logger = logging.getLogger(__name__)


def get_client_ip(request: Request, trust_proxy: bool = False) -> str:
    """
    Extract client IP from request, optionally trusting proxy headers.

    Args:
        request: Starlette request object
        trust_proxy: If True, check X-Forwarded-For header first

    Returns:
        Client IP address string, or "unknown" if unavailable
    """
    if trust_proxy:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def load_api_key() -> str:
    """
    Load or generate API key. Shared by MCP and REST auth.

    Priority:
    1. LLMC_MCP_API_KEY environment variable
    2. ~/.llmc/mcp-api-key file
    3. Auto-generate and save to ~/.llmc/mcp-api-key

    Returns:
        The API key string
    """
    env_key = os.getenv("LLMC_MCP_API_KEY")
    if env_key:
        logger.info("API key loaded from LLMC_MCP_API_KEY")
        return env_key

    key_path = Path.home() / ".llmc" / "mcp-api-key"
    if key_path.exists():
        try:
            key = key_path.read_text().strip()
            logger.info(f"API key loaded from {key_path}")
            return key
        except Exception as exc:
            logger.warning(f"Failed to load API key from {key_path}: {exc}")

    key = secrets.token_urlsafe(32)

    try:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(key)
        key_path.chmod(0o600)
        logger.info(f"Generated new API key and saved to {key_path}")
    except Exception as exc:
        logger.error(f"Failed to save API key to {key_path}: {exc}")
        logger.warning("API key is ephemeral - will change on restart!")

    return key


LOOPBACK_ADDRS = frozenset(["127.0.0.1", "::1", "localhost"])


def is_loopback(ip: str) -> bool:
    """Check if IP address is a loopback address."""
    return ip in LOOPBACK_ADDRS
