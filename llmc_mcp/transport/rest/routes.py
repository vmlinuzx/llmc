"""REST API route handlers."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any
import uuid

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


def parse_int_param(request: Request, name: str, default: int) -> int | str:
    """
    Safely parse an integer query parameter.
    
    Returns:
        int value if valid (or default if not provided), or error string if invalid
    """
    value = request.query_params.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return f"Parameter '{name}' must be an integer, got '{value}'"


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
        timestamp=datetime.now(UTC).isoformat(),
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

    limit_raw = parse_int_param(request, "limit", 20)
    if isinstance(limit_raw, str):
        return add_request_id(error_response("invalid_request", limit_raw, 400), request)
    limit = clamp_limit(limit_raw, config)
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
    get_config(request)
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
            error_response("index_not_found", "RAG index not built for workspace", 503),
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

    limit_raw = parse_int_param(request, "limit", 20)
    if isinstance(limit_raw, str):
        return add_request_id(error_response("invalid_request", limit_raw, 400), request)
    limit = clamp_limit(limit_raw, config)
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
            error_response("index_not_found", "RAG index not built for workspace", 503),
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

    limit_raw = parse_int_param(request, "limit", 20)
    if isinstance(limit_raw, str):
        return add_request_id(error_response("invalid_request", limit_raw, 400), request)
    limit = clamp_limit(limit_raw, config, default=20)

    # Clamp depth to 1-3
    depth_raw = parse_int_param(request, "depth", 1)
    if isinstance(depth_raw, str):
        return add_request_id(error_response("invalid_request", depth_raw, 400), request)
    max(1, min(3, depth_raw))

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
            error_response("index_not_found", "RAG index not built for workspace", 503),
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
    get_config(request)
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
