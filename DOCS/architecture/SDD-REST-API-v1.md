# SDD: REST API v1 for LLMC RAG Engine — FINAL

**Authors:** GPT-5.2 (draft), Gemini 3 Pro (review), Opus 4.5 (arbitration)  
**Date:** 2026-01-16  
**Status:** APPROVED FOR IMPLEMENTATION  
**Parent HLD:** [HLD-REST-API-v1.md](./HLD-REST-API-v1.md)

---

## Decision Log (Arbitration)

This document incorporates resolutions from the review cycle. All BLOCKER issues have been addressed.

| Issue | Severity | Resolution | Implementation Detail |
|-------|----------|------------|----------------------|
| Serialization Failure | BLOCKER | REQUIRE FIX | All endpoints use explicit `.to_dict()` serialization before JSONResponse |
| Missing Configuration Logic | BLOCKER | REQUIRE FIX | New `RestApiConfig` and `WorkspacesConfig` dataclasses added to `config.py` |
| Argument Mismatch (`limit` vs `max_results`) | BLOCKER | REQUIRE FIX | Explicit parameter mapping in endpoint handlers documented |
| API Key Loading Hack | CONCERN | REQUIRE REFACTOR | Extract `load_api_key()` as standalone function in `auth.py` |
| IP Resolution Duplication | CONCERN | REQUIRE REFACTOR | Add `get_client_ip()` utility in `transport/utils.py` |
| Missing Response Models | CONCERN | REQUIRE ADDITION | Complete response models in `schemas.py` |
| Exception Handler Missing | CONCERN | REQUIRE ADDITION | Global exception handler in `create_rest_api()` |

---

## 1. Scope

This SDD specifies the **implementation details** for the REST API v1. Developers should be able to implement this mechanically without architectural decisions.

### 1.1 What This Document Covers

- Exact file locations and module structure
- Complete function signatures with types
- Configuration dataclass definitions
- Request/response serialization patterns
- Error handling implementation
- Middleware integration order

### 1.2 Prerequisites

- Familiarity with [HLD-REST-API-v1.md](./HLD-REST-API-v1.md)
- Understanding of Starlette async patterns
- Access to `llmc/rag_nav/models.py` dataclass definitions

---

## 2. Configuration Implementation

### 2.1 New Config Dataclasses

Add to `llmc_mcp/config.py`:

```python
# llmc_mcp/config.py - NEW ADDITIONS

from dataclasses import dataclass, field


@dataclass
class RestApiConfig:
    """REST API transport settings."""

    enabled: bool = True
    auth_mode: str = "auto"  # "auto" | "token" | "none"
    rate_limit_rpm: int = 60
    rate_limit_burst: int = 10
    trust_proxy: bool = False
    max_results: int = 100

    def validate(self) -> None:
        if self.auth_mode not in ("auto", "token", "none"):
            raise ValueError(f"Invalid auth_mode: {self.auth_mode}")
        if self.rate_limit_rpm <= 0:
            raise ValueError("rate_limit_rpm must be positive")
        if self.max_results <= 0 or self.max_results > 1000:
            raise ValueError("max_results must be between 1 and 1000")


@dataclass
class WorkspacesConfig:
    """Workspace mappings for multi-repo support."""

    default: str | None = None
    repos: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if self.default and self.default not in self.repos:
            raise ValueError(f"Default workspace '{self.default}' not in repos")
        for name, path in self.repos.items():
            if not Path(path).is_absolute():
                raise ValueError(f"Workspace '{name}' path must be absolute: {path}")


# Modify McpConfig to include new fields:
@dataclass
class McpConfig:
    """Root MCP configuration."""

    enabled: bool = True
    config_version: str = "v0"
    mode: str = "classic"
    server: McpServerConfig = field(default_factory=McpServerConfig)
    auth: McpAuthConfig = field(default_factory=McpAuthConfig)
    tools: McpToolsConfig = field(default_factory=McpToolsConfig)
    rag: McpRagConfig = field(default_factory=McpRagConfig)
    limits: McpLimitsConfig = field(default_factory=McpLimitsConfig)
    observability: McpObservabilityConfig = field(default_factory=McpObservabilityConfig)
    code_execution: McpCodeExecutionConfig = field(default_factory=McpCodeExecutionConfig)
    hybrid: HybridConfig = field(default_factory=HybridConfig)
    linux_ops: LinuxOpsConfig = field(default_factory=LinuxOpsConfig)
    # NEW: REST API configuration
    rest_api: RestApiConfig = field(default_factory=RestApiConfig)
    workspaces: WorkspacesConfig = field(default_factory=WorkspacesConfig)

    def validate(self) -> None:
        # ... existing validations ...
        self.rest_api.validate()
        self.workspaces.validate()
```

### 2.2 Config Loading Updates

Add to `load_config()` in `llmc_mcp/config.py`:

```python
def load_config(config_path: str | Path | None = None) -> McpConfig:
    # ... existing code ...

    # REST API config
    rest_api = mcp_data.get("rest_api", {})
    cfg.rest_api.enabled = rest_api.get("enabled", cfg.rest_api.enabled)
    cfg.rest_api.auth_mode = rest_api.get("auth_mode", cfg.rest_api.auth_mode)
    cfg.rest_api.rate_limit_rpm = rest_api.get("rate_limit_rpm", cfg.rest_api.rate_limit_rpm)
    cfg.rest_api.rate_limit_burst = rest_api.get("rate_limit_burst", cfg.rest_api.rate_limit_burst)
    cfg.rest_api.trust_proxy = rest_api.get("trust_proxy", cfg.rest_api.trust_proxy)
    cfg.rest_api.max_results = rest_api.get("max_results", cfg.rest_api.max_results)

    # Workspaces config
    workspaces = mcp_data.get("workspaces", {})
    cfg.workspaces.default = workspaces.get("default", cfg.workspaces.default)
    cfg.workspaces.repos = workspaces.get("repos", cfg.workspaces.repos)

    # ... rest of function ...
```

---

## 3. Transport Utilities

### 3.1 Shared Utilities Module

Create `llmc_mcp/transport/utils.py`:

```python
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
            # X-Forwarded-For: client, proxy1, proxy2
            # First entry is the original client
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
    key = secrets.token_urlsafe(32)

    # Save to file with restrictive permissions
    try:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(key)
        key_path.chmod(0o600)
        logger.info(f"Generated new API key and saved to {key_path}")
    except Exception as e:
        logger.error(f"Failed to save API key to {key_path}: {e}")
        logger.warning("API key is ephemeral - will change on restart!")

    return key


# Loopback addresses that bypass authentication in "auto" mode
LOOPBACK_ADDRS = frozenset(["127.0.0.1", "::1", "localhost"])


def is_loopback(ip: str) -> bool:
    """Check if IP address is a loopback address."""
    return ip in LOOPBACK_ADDRS
```

### 3.2 Update Existing APIKeyMiddleware

Modify `llmc_mcp/transport/auth.py` to use shared utility:

```python
"""API key authentication middleware for HTTP transport."""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from llmc_mcp.transport.utils import load_api_key  # NEW: Use shared utility

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    API key validation middleware for MCP HTTP transport.
    (Unchanged from original - kept for MCP routes)
    """

    def __init__(self, app, api_key: str | None = None):
        super().__init__(app)
        # Use shared loader instead of internal method
        self.api_key = api_key or load_api_key()
        logger.info("API key authentication enabled")

    # Remove _load_or_generate_key and _generate_and_save_key methods
    # They are now in utils.py as load_api_key()

    async def dispatch(self, request: Request, call_next) -> Response:
        # ... unchanged from original ...
```

---

## 4. REST Authentication Middleware

Create `llmc_mcp/transport/rest_auth.py`:

```python
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
        # Health endpoint is always public
        if request.url.path.endswith("/health"):
            return await call_next(request)

        # No auth mode - skip validation
        if self.auth_mode == "none":
            return await call_next(request)

        # Get client IP
        client_ip = get_client_ip(request, self.trust_proxy)

        # Auto mode: bypass for loopback
        if self.auth_mode == "auto" and is_loopback(client_ip):
            return await call_next(request)

        # Auth required - validate API key
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
```

---

## 5. Rate Limiting Middleware

Create `llmc_mcp/transport/rest/middleware.py`:

```python
"""Rate limiting middleware for REST API."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from llmc_mcp.transport.utils import get_client_ip

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    tokens: float
    last_update: float


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP rate limiting using token bucket algorithm.

    Adds headers to all responses:
    - X-RateLimit-Limit: Requests per minute
    - X-RateLimit-Remaining: Tokens remaining
    - X-RateLimit-Reset: Unix timestamp when bucket refills
    """

    def __init__(
        self,
        app,
        rpm: int = 60,
        burst: int = 10,
        trust_proxy: bool = False,
    ):
        """
        Initialize rate limiter.

        Args:
            app: ASGI app to wrap
            rpm: Requests per minute limit
            burst: Maximum burst size (bucket capacity)
            trust_proxy: Trust X-Forwarded-For for client IP
        """
        super().__init__(app)
        self.rpm = rpm
        self.burst = burst
        self.trust_proxy = trust_proxy
        self.buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(tokens=burst, last_update=time.time())
        )
        # Refill rate: tokens per second
        self.refill_rate = rpm / 60.0

    def _get_bucket(self, ip: str) -> TokenBucket:
        """Get or create token bucket for IP, applying refill."""
        bucket = self.buckets[ip]
        now = time.time()
        elapsed = now - bucket.last_update

        # Refill tokens based on elapsed time
        bucket.tokens = min(self.burst, bucket.tokens + elapsed * self.refill_rate)
        bucket.last_update = now

        return bucket

    async def dispatch(self, request: Request, call_next) -> Response:
        """Check rate limit before forwarding request."""
        client_ip = get_client_ip(request, self.trust_proxy)
        bucket = self._get_bucket(client_ip)

        # Calculate reset time (when bucket would be full)
        tokens_needed = self.burst - bucket.tokens
        reset_seconds = tokens_needed / self.refill_rate if tokens_needed > 0 else 0
        reset_time = int(time.time() + reset_seconds)

        # Check if request can proceed
        if bucket.tokens < 1:
            return JSONResponse(
                {
                    "error": {
                        "code": "rate_limited",
                        "message": "Rate limit exceeded. Try again later.",
                        "details": {
                            "retry_after_seconds": int(1 / self.refill_rate),
                        },
                    }
                },
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(self.rpm),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(int(1 / self.refill_rate)),
                },
            )

        # Consume a token
        bucket.tokens -= 1

        # Forward request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.rpm)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response
```

---

## 6. Response Schemas

Create `llmc_mcp/transport/rest/schemas.py`:

```python
"""Response models for REST API endpoints."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ErrorDetail:
    """Structured error response."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"code": self.code, "message": self.message}
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class ErrorResponse:
    """Top-level error envelope."""

    error: ErrorDetail

    def to_dict(self) -> dict:
        return {"error": self.error.to_dict()}


@dataclass
class PaginationInfo:
    """Pagination metadata for list responses."""

    cursor: str | None = None
    has_more: bool = False
    total_estimate: int | None = None
    total: int | None = None

    def to_dict(self) -> dict:
        d = {"has_more": self.has_more}
        if self.cursor:
            d["cursor"] = self.cursor
        if self.total_estimate is not None:
            d["total_estimate"] = self.total_estimate
        if self.total is not None:
            d["total"] = self.total
        return d


@dataclass
class SearchMeta:
    """Metadata for search responses."""

    search_time_ms: int
    route: str = "code"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkspaceInfo:
    """Workspace metadata."""

    id: str
    path: str
    indexed: bool
    span_count: int | None = None
    last_indexed: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "path": self.path,
            "indexed": self.indexed,
            "span_count": self.span_count,
            "last_indexed": self.last_indexed,
        }


@dataclass
class HealthResponse:
    """Health check response."""

    status: str = "ok"
    version: str = "1.0.0"
    api: str = "rest"
    workspaces: list[str] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SpanResult:
    """Single search result span."""

    path: str
    kind: str
    name: str
    start_line: int
    end_line: int
    content: str
    docstring: str | None = None
    score: float = 0.0
    file_description: str | None = None
    language: str | None = None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "span": {
                "kind": self.kind,
                "name": self.name,
                "start_line": self.start_line,
                "end_line": self.end_line,
                "content": self.content,
                "docstring": self.docstring,
            },
            "score": self.score,
            "file_description": self.file_description,
            "language": self.language,
        }


@dataclass
class ReferenceResult:
    """Single reference/usage result."""

    path: str
    line: int
    context: str
    kind: str = "reference"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LineageNode:
    """Single node in lineage graph."""

    symbol: str
    path: str
    line: int
    depth: int = 1

    def to_dict(self) -> dict:
        return asdict(self)
```

---

## 7. REST Application Factory

Create `llmc_mcp/transport/rest/app.py`:

```python
"""REST API application factory."""

from __future__ import annotations

import logging
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    from starlette.types import ASGIApp

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
```

---

## 8. Route Handlers

Create `llmc_mcp/transport/rest/routes.py`:

```python
"""REST API route handlers."""

from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse

from llmc_mcp.transport.rest.schemas import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    PaginationInfo,
    SearchMeta,
    WorkspaceInfo,
)

if TYPE_CHECKING:
    from llmc_mcp.config import McpConfig

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================


def get_config(request: Request) -> McpConfig:
    """Extract config from app state."""
    return request.app.state.config


def resolve_workspace(request: Request, workspace_id: str) -> Path | None:
    """
    Resolve workspace ID to filesystem path.

    Returns:
        Path if found, None if workspace not configured
    """
    config = get_config(request)
    workspaces = config.workspaces

    # Check explicit mapping
    if workspace_id in workspaces.repos:
        return Path(workspaces.repos[workspace_id])

    # Check _default alias
    if workspace_id == "_default" and workspaces.default:
        if workspaces.default in workspaces.repos:
            return Path(workspaces.repos[workspaces.default])

    return None


def clamp_limit(limit: int | None, config: McpConfig, default: int = 20) -> int:
    """Clamp limit parameter to valid range."""
    if limit is None:
        return default
    return max(1, min(limit, config.rest_api.max_results))


def encode_cursor(offset: int) -> str:
    """Encode offset as opaque cursor."""
    return base64.urlsafe_b64encode(json.dumps({"offset": offset}).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    """Decode cursor to offset. Returns 0 for invalid/missing cursor."""
    if not cursor:
        return 0
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return int(data.get("offset", 0))
    except Exception:
        return 0


def error_response(code: str, message: str, status: int, **details: Any) -> JSONResponse:
    """Create standardized error response."""
    error = ErrorResponse(error=ErrorDetail(code=code, message=message, details=details))
    return JSONResponse(error.to_dict(), status_code=status)


def add_request_id(response: JSONResponse, request: Request) -> JSONResponse:
    """Add X-Request-ID header to response."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response.headers["X-Request-ID"] = request_id
    return response


# =============================================================================
# Endpoint Handlers
# =============================================================================


async def get_health(request: Request) -> JSONResponse:
    """
    GET /api/v1/health

    REST API health check.
    """
    config = get_config(request)
    workspaces = list(config.workspaces.repos.keys())

    response = HealthResponse(
        status="ok",
        version="1.0.0",
        api="rest",
        workspaces=workspaces,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    return add_request_id(JSONResponse(response.to_dict()), request)


async def get_workspaces(request: Request) -> JSONResponse:
    """
    GET /api/v1/workspaces

    List all configured workspaces with index status.
    """
    config = get_config(request)
    workspaces_info: list[dict] = []

    for ws_id, ws_path in config.workspaces.repos.items():
        path = Path(ws_path)
        rag_dir = path / ".rag"
        indexed = rag_dir.exists() and (rag_dir / "index.db").exists()

        info = WorkspaceInfo(
            id=ws_id,
            path=str(path),
            indexed=indexed,
            span_count=None,  # TODO: Read from index metadata
            last_indexed=None,  # TODO: Read from index metadata
        )
        workspaces_info.append(info.to_dict())

    return add_request_id(
        JSONResponse({
            "workspaces": workspaces_info,
            "default": config.workspaces.default,
        }),
        request,
    )


async def search(request: Request) -> JSONResponse:
    """
    GET /api/v1/workspaces/{workspace_id}/search

    Semantic search over code spans.
    """
    start_time = time.perf_counter()
    config = get_config(request)
    workspace_id = request.path_params["workspace_id"]

    # Resolve workspace
    repo_root = resolve_workspace(request, workspace_id)
    if repo_root is None:
        return add_request_id(
            error_response("workspace_not_found", f"Workspace '{workspace_id}' not configured", 404),
            request,
        )

    # Parse query parameters
    query = request.query_params.get("q", "").strip()
    if not query:
        return add_request_id(
            error_response("invalid_request", "Query parameter 'q' is required", 400),
            request,
        )

    limit = clamp_limit(
        int(request.query_params.get("limit", 20)) if request.query_params.get("limit") else None,
        config,
    )
    cursor = request.query_params.get("cursor")
    offset = decode_cursor(cursor)

    # Import RAG search (lazy to avoid circular imports)
    from llmc.rag.search import search_spans

    # CRITICAL: Wrap blocking RAG call in threadpool
    try:
        results = await run_in_threadpool(
            search_spans,
            query,
            limit=limit + offset + 1,  # Fetch extra to check has_more
            repo_root=repo_root,
        )
    except FileNotFoundError:
        return add_request_id(
            error_response(
                "index_not_found",
                f"RAG index not built for workspace '{workspace_id}'. Run 'llmc-cli rag index' first.",
                503,
            ),
            request,
        )

    # Apply offset pagination
    paginated = results[offset : offset + limit]
    has_more = len(results) > offset + limit

    # CRITICAL: Serialize dataclasses to dict
    # Results are SearchSpanResult dataclasses with to_dict() or use asdict()
    results_dict = []
    for r in paginated:
        if hasattr(r, "to_dict"):
            results_dict.append(r.to_dict())
        else:
            from dataclasses import asdict
            results_dict.append(asdict(r))

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    response_data = {
        "query": query,
        "workspace": workspace_id,
        "results": results_dict,
        "pagination": PaginationInfo(
            cursor=encode_cursor(offset + limit) if has_more else None,
            has_more=has_more,
            total_estimate=len(results) if len(results) <= 100 else None,
        ).to_dict(),
        "meta": SearchMeta(search_time_ms=elapsed_ms).to_dict(),
    }

    return add_request_id(JSONResponse(response_data), request)


async def get_symbol(request: Request) -> JSONResponse:
    """
    GET /api/v1/workspaces/{workspace_id}/symbols/{name}

    Get detailed information about a symbol.
    """
    start_time = time.perf_counter()
    config = get_config(request)
    workspace_id = request.path_params["workspace_id"]
    symbol_name = request.path_params["name"]

    repo_root = resolve_workspace(request, workspace_id)
    if repo_root is None:
        return add_request_id(
            error_response("workspace_not_found", f"Workspace '{workspace_id}' not configured", 404),
            request,
        )

    # Use RAG search to find symbol definition
    from llmc.rag.search import search_spans

    try:
        results = await run_in_threadpool(
            search_spans,
            symbol_name,
            limit=10,
            repo_root=repo_root,
        )
    except FileNotFoundError:
        return add_request_id(
            error_response("index_not_found", f"RAG index not built for workspace", 503),
            request,
        )

    # Find exact match
    definition = None
    for r in results:
        if hasattr(r, "symbol") and r.symbol == symbol_name:
            definition = r
            break

    if definition is None and results:
        # Fallback to first result
        definition = results[0]

    if definition is None:
        return add_request_id(
            error_response("symbol_not_found", f"Symbol '{symbol_name}' not found in index", 404),
            request,
        )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    # Serialize result
    if hasattr(definition, "to_dict"):
        def_dict = definition.to_dict()
    else:
        from dataclasses import asdict
        def_dict = asdict(definition)

    return add_request_id(
        JSONResponse({
            "symbol": symbol_name,
            "workspace": workspace_id,
            "definition": def_dict,
            "meta": {"lookup_time_ms": elapsed_ms},
        }),
        request,
    )


async def get_symbol_references(request: Request) -> JSONResponse:
    """
    GET /api/v1/workspaces/{workspace_id}/symbols/{name}/references

    Find all usages of a symbol.
    """
    start_time = time.perf_counter()
    config = get_config(request)
    workspace_id = request.path_params["workspace_id"]
    symbol_name = request.path_params["name"]

    repo_root = resolve_workspace(request, workspace_id)
    if repo_root is None:
        return add_request_id(
            error_response("workspace_not_found", f"Workspace '{workspace_id}' not configured", 404),
            request,
        )

    limit = clamp_limit(
        int(request.query_params.get("limit", 20)) if request.query_params.get("limit") else None,
        config,
    )
    cursor = request.query_params.get("cursor")
    offset = decode_cursor(cursor)

    # Import where-used tool
    from llmc.rag_nav.tool_handlers import tool_rag_where_used

    try:
        # CRITICAL: Map API 'limit' parameter correctly
        result = await run_in_threadpool(
            tool_rag_where_used,
            repo_root,
            symbol_name,
            limit=limit + offset + 1,  # Fetch extra for pagination
        )
    except FileNotFoundError:
        return add_request_id(
            error_response("index_not_found", f"RAG index not built for workspace", 503),
            request,
        )

    # CRITICAL: Serialize WhereUsedResult dataclass using .to_dict()
    result_dict = result.to_dict()
    items = result_dict.get("items", [])

    # Apply pagination
    paginated_items = items[offset : offset + limit]
    has_more = len(items) > offset + limit

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    return add_request_id(
        JSONResponse({
            "symbol": symbol_name,
            "workspace": workspace_id,
            "references": paginated_items,
            "pagination": PaginationInfo(
                cursor=encode_cursor(offset + limit) if has_more else None,
                has_more=has_more,
                total=len(items),
            ).to_dict(),
            "meta": {"search_time_ms": elapsed_ms},
        }),
        request,
    )


async def get_symbol_lineage(request: Request) -> JSONResponse:
    """
    GET /api/v1/workspaces/{workspace_id}/symbols/{name}/lineage

    Get call graph for a symbol.
    """
    start_time = time.perf_counter()
    config = get_config(request)
    workspace_id = request.path_params["workspace_id"]
    symbol_name = request.path_params["name"]

    repo_root = resolve_workspace(request, workspace_id)
    if repo_root is None:
        return add_request_id(
            error_response("workspace_not_found", f"Workspace '{workspace_id}' not configured", 404),
            request,
        )

    # Parse parameters
    direction = request.query_params.get("direction", "both")
    if direction not in ("callers", "callees", "both"):
        direction = "both"

    limit = clamp_limit(
        int(request.query_params.get("limit", 20)) if request.query_params.get("limit") else None,
        config,
        default=20,
    )

    # Clamp depth to 1-3
    depth = int(request.query_params.get("depth", 1))
    depth = max(1, min(3, depth))

    from llmc.rag_nav.tool_handlers import tool_rag_lineage

    try:
        # CRITICAL: Map API 'limit' to backend 'max_results' parameter
        result = await run_in_threadpool(
            tool_rag_lineage,
            repo_root,
            symbol_name,
            direction,
            max_results=limit,  # Explicit mapping: API 'limit' -> backend 'max_results'
        )
    except FileNotFoundError:
        return add_request_id(
            error_response("index_not_found", f"RAG index not built for workspace", 503),
            request,
        )

    # CRITICAL: Serialize LineageResult dataclass using .to_dict()
    result_dict = result.to_dict()

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    return add_request_id(
        JSONResponse({
            "symbol": symbol_name,
            "workspace": workspace_id,
            "direction": result_dict.get("direction", direction),
            "callers": result_dict.get("items", []) if direction in ("callers", "both") else [],
            "callees": result_dict.get("items", []) if direction in ("callees", "both") else [],
            "meta": {"search_time_ms": elapsed_ms},
        }),
        request,
    )


async def get_file(request: Request) -> JSONResponse:
    """
    GET /api/v1/workspaces/{workspace_id}/files/{file_path}

    Get file content with RAG context.
    """
    start_time = time.perf_counter()
    config = get_config(request)
    workspace_id = request.path_params["workspace_id"]
    file_path = request.path_params["file_path"]

    repo_root = resolve_workspace(request, workspace_id)
    if repo_root is None:
        return add_request_id(
            error_response("workspace_not_found", f"Workspace '{workspace_id}' not configured", 404),
            request,
        )

    full_path = repo_root / file_path

    # Security: Ensure path is within workspace
    try:
        full_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return add_request_id(
            error_response("invalid_request", "Path traversal not allowed", 400),
            request,
        )

    if not full_path.exists():
        return add_request_id(
            error_response("file_not_found", f"File not found: {file_path}", 404),
            request,
        )

    if not full_path.is_file():
        return add_request_id(
            error_response("invalid_request", f"Path is not a file: {file_path}", 400),
            request,
        )

    # Read file content
    try:
        content = await run_in_threadpool(full_path.read_text, encoding="utf-8")
    except UnicodeDecodeError:
        return add_request_id(
            error_response("invalid_request", "File is not valid UTF-8 text", 400),
            request,
        )

    # Determine language from extension
    ext_to_lang = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "jsx",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
    }
    language = ext_to_lang.get(full_path.suffix.lower(), "text")

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    return add_request_id(
        JSONResponse({
            "path": file_path,
            "workspace": workspace_id,
            "content": content,
            "language": language,
            "line_count": content.count("\n") + 1,
            "meta": {"read_time_ms": elapsed_ms},
        }),
        request,
    )
```

---

## 9. HTTP Server Integration

### 9.1 Mount Point in http_server.py

Modify `llmc_mcp/transport/http_server.py`:

```python
# In HttpMcpServer.__init__ or equivalent setup method:

from llmc_mcp.transport.rest.app import create_rest_api

def _setup_routes(self, config: McpConfig) -> list[BaseRoute]:
    """Build route list with REST API mounted first."""
    routes: list[BaseRoute] = []

    # Mount REST API if enabled
    if config.rest_api.enabled:
        rest_app = create_rest_api(config)
        routes.append(Mount("/api/v1", app=rest_app))
        logger.info("REST API mounted at /api/v1")

    # Existing MCP routes (unchanged)
    routes.extend([
        Route("/health", endpoint=self._health),
        Route("/sse", endpoint=self._handle_sse),
        Mount("/messages", app=self.sse_transport.handle_post_message),
    ])

    return routes
```

---

## 10. File Structure Summary

```
llmc_mcp/
├── config.py                    # MODIFY: Add RestApiConfig, WorkspacesConfig
├── transport/
│   ├── __init__.py
│   ├── auth.py                  # MODIFY: Use load_api_key from utils
│   ├── rest_auth.py             # NEW: RestAuthMiddleware
│   ├── http_server.py           # MODIFY: Mount REST sub-app
│   ├── utils.py                 # NEW: Shared utilities
│   └── rest/
│       ├── __init__.py          # NEW
│       ├── app.py               # NEW: create_rest_api()
│       ├── routes.py            # NEW: Endpoint handlers
│       ├── schemas.py           # NEW: Response models
│       └── middleware.py        # NEW: RateLimitMiddleware
```

---

## 11. Testing Requirements

### 11.1 Unit Tests

| Test File | Coverage |
|-----------|----------|
| `tests/rest/test_utils.py` | `get_client_ip`, `load_api_key`, `is_loopback` |
| `tests/rest/test_auth.py` | `RestAuthMiddleware` modes: auto, token, none |
| `tests/rest/test_rate_limit.py` | Token bucket algorithm, header injection |
| `tests/rest/test_routes.py` | Each endpoint handler in isolation |
| `tests/rest/test_serialization.py` | Dataclass `.to_dict()` serialization |

### 11.2 Integration Tests

| Test File | Coverage |
|-----------|----------|
| `tests/rest/test_integration.py` | Full request/response with test index |
| `tests/rest/test_auth_integration.py` | Loopback bypass, API key validation |

### 11.3 Test Fixtures

```python
# tests/rest/conftest.py

import pytest
from starlette.testclient import TestClient
from llmc_mcp.config import McpConfig, RestApiConfig, WorkspacesConfig
from llmc_mcp.transport.rest.app import create_rest_api


@pytest.fixture
def test_config(tmp_path):
    """Config with test workspace."""
    return McpConfig(
        rest_api=RestApiConfig(auth_mode="none"),  # Disable auth for tests
        workspaces=WorkspacesConfig(
            default="test",
            repos={"test": str(tmp_path)},
        ),
    )


@pytest.fixture
def rest_client(test_config):
    """Test client for REST API."""
    app = create_rest_api(test_config)
    return TestClient(app)
```

---

## 12. Implementation Checklist

### Phase 1: Foundation (Priority: P0)

- [ ] Add `RestApiConfig` and `WorkspacesConfig` to `config.py`
- [ ] Add config loading for new sections
- [ ] Create `transport/utils.py` with shared utilities
- [ ] Refactor `APIKeyMiddleware` to use `load_api_key()`
- [ ] Create `transport/rest/__init__.py`

### Phase 2: Middleware (Priority: P0)

- [ ] Implement `RestAuthMiddleware`
- [ ] Implement `RateLimitMiddleware`
- [ ] Write unit tests for both

### Phase 3: Endpoints (Priority: P0)

- [ ] Implement `get_health`
- [ ] Implement `get_workspaces`
- [ ] Implement `search` with serialization
- [ ] Implement `get_symbol`
- [ ] Implement `get_symbol_references` with correct parameter mapping
- [ ] Implement `get_symbol_lineage` with `limit` → `max_results` mapping

### Phase 4: Integration (Priority: P1)

- [ ] Create `create_rest_api()` factory
- [ ] Add global exception handler
- [ ] Mount in `http_server.py`
- [ ] Integration tests

### Phase 5: Polish (Priority: P2)

- [ ] Request ID generation
- [ ] Structured logging
- [ ] OpenAPI spec generation (optional)

---

## Appendix A: Parameter Mapping Reference

| Endpoint | API Parameter | Backend Parameter | Notes |
|----------|---------------|-------------------|-------|
| `/search` | `limit` | `limit` | Direct mapping |
| `/symbols/{name}/references` | `limit` | `limit` | Direct mapping |
| `/symbols/{name}/lineage` | `limit` | `max_results` | **MUST MAP** |
| `/symbols/{name}/lineage` | `direction` | `direction` | Normalize to "upstream"/"downstream" |

---

## Appendix B: Serialization Patterns

All RAG result types have `.to_dict()` methods. Always use them:

```python
# CORRECT: Use .to_dict()
result = await run_in_threadpool(tool_rag_lineage, ...)
return JSONResponse({"data": result.to_dict()})

# ALSO CORRECT: Fallback for types without .to_dict()
from dataclasses import asdict
result_dict = result.to_dict() if hasattr(result, 'to_dict') else asdict(result)

# WRONG: Will fail with JSONResponse
return JSONResponse({"data": result})  # TypeError: Object is not JSON serializable
```

---

## Approval

This SDD has been reviewed and approved for implementation.

---
FINAL_VERDICT: APPROVED
REQUIRED_CHANGES: None (all incorporated above)
OPTIONAL_IMPROVEMENTS: OpenAPI spec generation for Phase 5
NEXT_STEPS: Begin Phase 1 implementation
ESCALATION: None
