# HLD: REST API v1 for LLMC RAG Engine — FINAL

**Authors:** GPT-5.2 (draft), Gemini 3 Pro (review), Opus 4.5 (decision)  
**Date:** 2026-01-16  
**Status:** READY FOR HUMAN REVIEW

---

## Decision Log

| Critique | Verdict | Rationale |
|----------|---------|-----------|
| Missing full API specification | ACCEPT | The complete OpenAPI-style spec is now included in Section 4 |
| Auth middleware architecture conflict | ACCEPT | New `RestAuthMiddleware` with loopback bypass specified; MCP auth untouched |
| Blocking event loop concerns | ACCEPT | Hard requirement added: all sync RAG calls MUST use `run_in_threadpool()` |
| Fake pagination criticism | ACCEPT | Documented honestly: v1 pagination is offset-based, not true cursor. Hard cap at 100. |
| Workspace config schema undefined | ACCEPT | Explicit TOML schema provided in Section 3.2 |
| Rate limiting scope unclear | ACCEPT | Clarified: per-IP by default, X-Forwarded-For configurable |
| Index not found error handling | ACCEPT | Returns 503 with `index_not_found` error code |
| Write operations undefined | ACCEPT | Confirmed read-only for v1; future `/reindex` endpoint noted |
| Health check ambiguity | ACCEPT | Two endpoints: `/health` (MCP), `/api/v1/health` (REST-specific) |

---

## 1. Overview

### 1.1 Purpose

Expose LLMC's RAG search capabilities via a standard REST/JSON API, enabling:
- IDE plugins (VS Code, JetBrains) to query the local index
- CI/CD pipelines to validate code changes against the knowledge base
- Custom tooling without MCP protocol complexity
- Programmatic access from any HTTP client

### 1.2 Non-Goals (v1)

- **Write operations**: No indexing, re-indexing, or mutations via REST. Index management remains CLI-only.
- **Real-time streaming**: No SSE/WebSocket for search results (MCP handles streaming use cases)
- **Multi-tenant auth**: Single-user, local-first deployment model
- **True cursor pagination**: v1 uses offset-based "fake" cursors (see Section 6.3)

### 1.3 Design Principles

1. **Additive only**: REST API is a new sub-application; zero changes to existing MCP routes
2. **Loopback-safe**: Local development should "just work" without API keys
3. **Thread-safe**: All blocking RAG operations offloaded to thread pool
4. **Honest limitations**: Document what works and what doesn't

---

## 2. Architecture

### 2.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Starlette Application                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  REST Sub-App (mounted at /api/v1)                            │   │
│  │  ┌──────────────────────────────────────────────────────────┐│   │
│  │  │  RestAuthMiddleware                                      ││   │
│  │  │  - Loopback bypass (127.0.0.1, ::1) when auth_mode=auto  ││   │
│  │  │  - API key required for non-loopback or auth_mode=token  ││   │
│  │  └──────────────────────────────────────────────────────────┘│   │
│  │  ┌──────────────────────────────────────────────────────────┐│   │
│  │  │  RateLimitMiddleware (per-IP, X-Forwarded-For aware)     ││   │
│  │  └──────────────────────────────────────────────────────────┘│   │
│  │                                                                │   │
│  │  Routes:                                                       │   │
│  │    GET  /api/v1/health                                        │   │
│  │    GET  /api/v1/workspaces                                    │   │
│  │    GET  /api/v1/workspaces/{id}/search                        │   │
│  │    GET  /api/v1/workspaces/{id}/symbols/{name}                │   │
│  │    GET  /api/v1/workspaces/{id}/symbols/{name}/references     │   │
│  │    GET  /api/v1/workspaces/{id}/symbols/{name}/lineage        │   │
│  │    GET  /api/v1/workspaces/{id}/files/{path:path}             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  MCP Routes (existing, unchanged)                              │   │
│  │  ┌──────────────────────────────────────────────────────────┐│   │
│  │  │  APIKeyMiddleware (existing)                              ││   │
│  │  └──────────────────────────────────────────────────────────┘│   │
│  │    GET  /health                                               │   │
│  │    GET  /sse                                                  │   │
│  │    POST /messages                                             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   RAG Service Layer           │
                    │   (search_spans, lineage,     │
                    │    where_used, etc.)          │
                    │                               │
                    │   ⚠️ SYNC - BLOCKING          │
                    │   Must wrap in threadpool!    │
                    └───────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   SQLite Index (.rag/)        │
                    └───────────────────────────────┘
```

### 2.2 Mount Order

The REST sub-app is mounted with its own middleware stack. Critical ordering:

```python
# In http_server.py

# 1. Create REST sub-app with its own middleware
rest_app = create_rest_api(config)
rest_app.add_middleware(RateLimitMiddleware, ...)
rest_app.add_middleware(RestAuthMiddleware, ...)

# 2. Mount REST sub-app FIRST (before MCP routes)
routes = [
    Mount("/api/v1", app=rest_app),  # REST with its own auth
    Route("/health", endpoint=self._health),  # MCP health (existing)
    Route("/sse", endpoint=self._handle_sse),  # MCP SSE
    Mount("/messages", app=self.sse_transport.handle_post_message),
]

# 3. MCP auth middleware applies to root app
app = Starlette(routes=routes, ...)
app.add_middleware(APIKeyMiddleware)  # Only affects non-mounted routes
```

This ensures:
- REST endpoints use `RestAuthMiddleware` (loopback bypass)
- MCP endpoints use existing `APIKeyMiddleware` (unchanged)
- No cross-contamination of auth strategies

---

## 3. Configuration

### 3.1 New Config Section

Add to `llmc.toml`:

```toml
[mcp.rest_api]
enabled = true                    # Enable REST API endpoints
auth_mode = "auto"                # "auto" | "token" | "none"
                                  # auto: loopback=no-auth, remote=require-token
                                  # token: always require API key
                                  # none: no auth (NOT RECOMMENDED)
rate_limit_rpm = 60               # Requests per minute per IP
rate_limit_burst = 10             # Burst allowance
trust_proxy = false               # Trust X-Forwarded-For header
max_results = 100                 # Hard cap on any limit parameter
```

### 3.2 Workspace Configuration

Define workspace mappings for multi-repo support:

```toml
[mcp.workspaces]
default = "llmc"                  # Default workspace ID

[mcp.workspaces.repos]
llmc = "/home/vmlinux/src/llmc"
myapp = "/home/vmlinux/src/myapp"
frontend = "/home/vmlinux/src/frontend"
```

**Workspace Resolution:**
1. If `{id}` matches a key in `workspaces.repos` → use that path
2. If `{id}` is `_default` → use `workspaces.default` key
3. Otherwise → 404 "Workspace not found"

### 3.3 Environment Overrides

| Variable | Config Path | Default |
|----------|-------------|---------|
| `LLMC_REST_ENABLED` | `mcp.rest_api.enabled` | `true` |
| `LLMC_REST_AUTH_MODE` | `mcp.rest_api.auth_mode` | `"auto"` |
| `LLMC_REST_RATE_LIMIT` | `mcp.rest_api.rate_limit_rpm` | `60` |

---

## 4. API Specification

### 4.1 Common Headers

**Request Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| `X-API-Key` | Conditional | Required when `auth_mode=token` or non-loopback with `auth_mode=auto` |
| `Accept` | No | `application/json` (default) |

**Response Headers:**
| Header | Description |
|--------|-------------|
| `X-Request-ID` | UUID for request tracing |
| `X-RateLimit-Remaining` | Requests remaining in window |
| `X-RateLimit-Reset` | Unix timestamp when window resets |

### 4.2 Error Response Format

All errors follow a consistent schema:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

**Error Codes:**

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `invalid_request` | Malformed request or invalid parameters |
| 401 | `unauthorized` | Missing or invalid API key |
| 404 | `workspace_not_found` | Workspace ID not configured |
| 404 | `symbol_not_found` | Symbol not in index |
| 404 | `file_not_found` | File path not in index |
| 429 | `rate_limited` | Rate limit exceeded |
| 503 | `index_not_found` | RAG index not built for workspace |
| 503 | `index_stale` | Index exists but may be outdated |

### 4.3 Endpoints

---

#### `GET /api/v1/health`

REST API health check (separate from MCP `/health`).

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "api": "rest",
  "workspaces": ["llmc", "myapp"],
  "timestamp": "2026-01-16T10:30:00Z"
}
```

---

#### `GET /api/v1/workspaces`

List all configured workspaces.

**Response:**
```json
{
  "workspaces": [
    {
      "id": "llmc",
      "path": "/home/vmlinux/src/llmc",
      "indexed": true,
      "span_count": 12450,
      "last_indexed": "2026-01-15T22:00:00Z"
    },
    {
      "id": "myapp",
      "path": "/home/vmlinux/src/myapp",
      "indexed": false,
      "span_count": null,
      "last_indexed": null
    }
  ],
  "default": "llmc"
}
```

---

#### `GET /api/v1/workspaces/{id}/search`

Semantic search over code spans.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `q` | string | Yes | - | Search query |
| `limit` | int | No | 20 | Max results (1-100) |
| `cursor` | string | No | - | Pagination cursor (opaque) |
| `filter.language` | string | No | - | Filter by language (`python`, `typescript`, etc.) |
| `filter.kind` | string | No | - | Filter by span kind (`function`, `class`, `method`) |
| `filter.path` | string | No | - | Filter by path prefix |
| `expand` | bool | No | false | Include full file content for top results |
| `expand_count` | int | No | 3 | Number of files to expand (when expand=true) |

**Response:**
```json
{
  "query": "authentication middleware",
  "workspace": "llmc",
  "results": [
    {
      "path": "llmc_mcp/transport/auth.py",
      "span": {
        "kind": "class",
        "name": "APIKeyMiddleware",
        "start_line": 21,
        "end_line": 138,
        "content": "class APIKeyMiddleware(BaseHTTPMiddleware):\n    ...",
        "docstring": "API key validation middleware for MCP HTTP transport."
      },
      "score": 0.892,
      "file_description": "API key authentication middleware for HTTP transport.",
      "language": "python"
    }
  ],
  "pagination": {
    "cursor": "eyJvZmZzZXQiOjIwfQ==",
    "has_more": true,
    "total_estimate": 47
  },
  "meta": {
    "search_time_ms": 45,
    "route": "code"
  }
}
```

**Pagination Note (v1 Limitation):**  
The `cursor` is a base64-encoded offset, not a true database cursor. Each page re-executes the full search with an offset. This provides:
- Stable ordering within a session
- Avoids URL length limits for complex queries
- **Does NOT provide**: Consistent results if index changes between requests

True cursor-based pagination requires index-level changes and is deferred to v2.

---

#### `GET /api/v1/workspaces/{id}/symbols/{name}`

Get detailed information about a symbol.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | Yes | Symbol name (e.g., `APIKeyMiddleware`, `search_spans`) |

**Response:**
```json
{
  "symbol": "APIKeyMiddleware",
  "workspace": "llmc",
  "definition": {
    "path": "llmc_mcp/transport/auth.py",
    "line": 21,
    "kind": "class",
    "signature": "class APIKeyMiddleware(BaseHTTPMiddleware)",
    "docstring": "API key validation middleware for MCP HTTP transport.\n\nValidates X-API-Key header...",
    "content": "class APIKeyMiddleware(BaseHTTPMiddleware):\n    ..."
  },
  "exports": [
    {
      "path": "llmc_mcp/transport/__init__.py",
      "line": 3
    }
  ],
  "meta": {
    "lookup_time_ms": 12
  }
}
```

---

#### `GET /api/v1/workspaces/{id}/symbols/{name}/references`

Find all usages of a symbol (who calls/uses this?).

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `name` | string | Yes | - | Symbol name |
| `limit` | int | No | 20 | Max results (1-100) |
| `cursor` | string | No | - | Pagination cursor |

**Response:**
```json
{
  "symbol": "APIKeyMiddleware",
  "workspace": "llmc",
  "references": [
    {
      "path": "llmc_mcp/transport/http_server.py",
      "line": 8,
      "context": "from llmc_mcp.transport.auth import APIKeyMiddleware",
      "kind": "import"
    },
    {
      "path": "llmc_mcp/transport/http_server.py",
      "line": 89,
      "context": "app.add_middleware(APIKeyMiddleware)",
      "kind": "call"
    },
    {
      "path": "tests/test_mcp_http_transport.py",
      "line": 161,
      "context": "class TestAPIKeyMiddleware:",
      "kind": "reference"
    }
  ],
  "pagination": {
    "cursor": null,
    "has_more": false,
    "total": 5
  },
  "meta": {
    "search_time_ms": 23
  }
}
```

---

#### `GET /api/v1/workspaces/{id}/symbols/{name}/lineage`

Get call graph for a symbol (callers and/or callees).

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `name` | string | Yes | - | Symbol name |
| `direction` | string | No | `both` | `callers`, `callees`, or `both` |
| `depth` | int | No | 1 | Traversal depth (1-3) |
| `limit` | int | No | 20 | Max results per direction (1-50) |

**Response:**
```json
{
  "symbol": "search_spans",
  "workspace": "llmc",
  "definition": {
    "path": "llmc/rag/search/__init__.py",
    "line": 346
  },
  "callers": [
    {
      "symbol": "mcgrep.search",
      "path": "llmc/mcgrep.py",
      "line": 111,
      "depth": 1
    },
    {
      "symbol": "run_search_spans",
      "path": "llmc/commands/rag.py",
      "line": 55,
      "depth": 1
    }
  ],
  "callees": [
    {
      "symbol": "Database.__init__",
      "path": "llmc/rag/database.py",
      "line": 45,
      "depth": 1
    },
    {
      "symbol": "create_router",
      "path": "llmc/rag/routing/router.py",
      "line": 78,
      "depth": 1
    }
  ],
  "meta": {
    "search_time_ms": 67
  }
}
```

---

#### `GET /api/v1/workspaces/{id}/files/{path:path}`

Get file content with RAG context.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | string | Yes | File path relative to workspace root |
| `include_spans` | bool | No | Include parsed spans (default: true) |
| `include_graph` | bool | No | Include import/export relationships (default: false) |

**Response:**
```json
{
  "path": "llmc_mcp/transport/auth.py",
  "workspace": "llmc",
  "content": "\"\"\"API key authentication middleware...\"\"\"\n\nfrom __future__ import annotations\n...",
  "language": "python",
  "line_count": 138,
  "spans": [
    {
      "kind": "class",
      "name": "APIKeyMiddleware",
      "start_line": 21,
      "end_line": 138,
      "methods": ["__init__", "_load_or_generate_key", "_generate_and_save_key", "dispatch"]
    }
  ],
  "graph": {
    "imports": [
      {"module": "starlette.middleware.base", "names": ["BaseHTTPMiddleware"]},
      {"module": "starlette.responses", "names": ["JSONResponse"]}
    ],
    "imported_by": [
      "llmc_mcp/transport/__init__.py",
      "llmc_mcp/transport/http_server.py"
    ]
  },
  "description": "API key authentication middleware for HTTP transport.",
  "meta": {
    "indexed_at": "2026-01-15T22:00:00Z",
    "read_time_ms": 8
  }
}
```

---

## 5. Authentication

### 5.1 RestAuthMiddleware

New middleware class specifically for REST API (does NOT modify existing `APIKeyMiddleware`):

```python
# llmc_mcp/transport/rest_auth.py

class RestAuthMiddleware(BaseHTTPMiddleware):
    """
    REST API authentication with loopback bypass.
    
    Behavior based on auth_mode:
    - "auto": Skip auth for loopback (127.0.0.1, ::1), require for remote
    - "token": Always require X-API-Key header
    - "none": No authentication (NOT RECOMMENDED)
    """
    
    LOOPBACK_ADDRS = frozenset(["127.0.0.1", "::1", "localhost"])
    
    def __init__(self, app, auth_mode: str = "auto", trust_proxy: bool = False):
        super().__init__(app)
        self.auth_mode = auth_mode
        self.trust_proxy = trust_proxy
        self.api_key = self._load_api_key()
    
    async def dispatch(self, request: Request, call_next):
        # Health endpoint is always public
        if request.url.path == "/api/v1/health":
            return await call_next(request)
        
        # Determine client IP
        client_ip = self._get_client_ip(request)
        
        # Check if auth is required
        if self.auth_mode == "none":
            return await call_next(request)
        
        if self.auth_mode == "auto" and self._is_loopback(client_ip):
            return await call_next(request)
        
        # Auth required - validate API key
        api_key = request.headers.get("X-API-Key")
        if not api_key or not secrets.compare_digest(api_key, self.api_key):
            return JSONResponse(
                {"error": {"code": "unauthorized", "message": "Invalid or missing API key"}},
                status_code=401
            )
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        if self.trust_proxy:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _is_loopback(self, ip: str) -> bool:
        return ip in self.LOOPBACK_ADDRS
```

### 5.2 API Key Management

REST API shares the same API key as MCP (loaded from same sources):

1. `LLMC_MCP_API_KEY` environment variable
2. `~/.llmc/mcp-api-key` file
3. Auto-generated on first run

---

## 6. Performance Requirements

### 6.1 Thread Pool Offloading (HARD REQUIREMENT)

**ALL calls to blocking RAG functions MUST be wrapped in `run_in_threadpool()`:**

```python
from starlette.concurrency import run_in_threadpool

async def search_endpoint(request: Request):
    # WRONG - blocks event loop:
    # results = search_spans(query, limit=limit, repo_root=repo_root)
    
    # CORRECT - offload to thread pool:
    results = await run_in_threadpool(
        search_spans,
        query,
        limit=limit,
        repo_root=repo_root
    )
    return JSONResponse({"results": results})
```

**Functions requiring thread pool wrapping:**
- `search_spans()` - Full-text + embedding search
- `tool_rag_where_used()` - Reference lookup
- `tool_rag_lineage()` - Call graph traversal
- Any function that touches SQLite index

### 6.2 Rate Limiting

- **Scope**: Per-IP address
- **Default**: 60 requests/minute, burst of 10
- **Proxy support**: When `trust_proxy=true`, uses `X-Forwarded-For` header
- **Implementation**: Token bucket algorithm

Rate limit headers on every response:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1705405800
```

### 6.3 Pagination Limits

| Parameter | Min | Max | Default |
|-----------|-----|-----|---------|
| `limit` | 1 | 100 | 20 |
| `depth` (lineage) | 1 | 3 | 1 |
| `expand_count` | 1 | 10 | 3 |

**Pagination Implementation (v1):**

The cursor-based pagination is "cosmetic" in v1:
- Cursor encodes offset: `base64({"offset": N})`
- Each page re-runs the full query with `OFFSET N`
- Results may shift if index is updated between requests

This is acceptable for v1 because:
1. Most use cases don't paginate beyond first page
2. Index updates are infrequent (CLI-triggered)
3. Cursor still provides value: stable sort order, avoids URL bloat

**Future (v2):** True cursor pagination requires:
- Keyset pagination in SQLite queries
- Snapshot isolation or versioned reads
- Significant index schema changes

---

## 7. Implementation Plan

### 7.1 File Structure

```
llmc_mcp/
├── transport/
│   ├── auth.py              # Existing APIKeyMiddleware (unchanged)
│   ├── rest_auth.py         # NEW: RestAuthMiddleware
│   ├── http_server.py       # Modified: mount REST sub-app
│   └── rest/
│       ├── __init__.py
│       ├── app.py           # NEW: create_rest_api()
│       ├── routes.py        # NEW: endpoint handlers
│       ├── schemas.py       # NEW: response models
│       └── middleware.py    # NEW: RateLimitMiddleware
```

### 7.2 Implementation Phases

**Phase 1: Foundation (Week 1)**
- [ ] Create `RestAuthMiddleware` with loopback bypass
- [ ] Create REST sub-app with mounting logic
- [ ] Implement `/api/v1/health` endpoint
- [ ] Implement `/api/v1/workspaces` endpoint
- [ ] Add config schema for `[mcp.rest_api]`

**Phase 2: Core Search (Week 2)**
- [ ] Implement `/api/v1/workspaces/{id}/search`
- [ ] Add thread pool wrapping for `search_spans`
- [ ] Implement pagination (offset-based)
- [ ] Add `expand` functionality for full file content

**Phase 3: Symbol APIs (Week 3)**
- [ ] Implement `/api/v1/workspaces/{id}/symbols/{name}`
- [ ] Implement `/api/v1/workspaces/{id}/symbols/{name}/references`
- [ ] Implement `/api/v1/workspaces/{id}/symbols/{name}/lineage`
- [ ] Add thread pool wrapping for all RAG calls

**Phase 4: Files & Polish (Week 4)**
- [ ] Implement `/api/v1/workspaces/{id}/files/{path}`
- [ ] Add `RateLimitMiddleware`
- [ ] Add request ID generation and logging
- [ ] Comprehensive error handling
- [ ] Integration tests

### 7.3 Testing Strategy

1. **Unit tests**: Each endpoint handler in isolation
2. **Integration tests**: Full request/response cycle with test index
3. **Auth tests**: Loopback bypass, API key validation, proxy trust
4. **Performance tests**: Verify thread pool prevents event loop blocking
5. **Rate limit tests**: Token bucket behavior

---

## 8. Migration & Compatibility

### 8.1 Backward Compatibility

- **MCP routes**: Completely unchanged
- **Existing auth**: `APIKeyMiddleware` untouched
- **Config**: New section is additive, old configs work

### 8.2 Feature Flag

REST API can be disabled entirely:

```toml
[mcp.rest_api]
enabled = false
```

When disabled, `/api/v1/*` routes return 404.

---

## 9. Security Considerations

1. **Loopback trust**: Only `127.0.0.1` and `::1` bypass auth; `0.0.0.0` does NOT
2. **Proxy trust**: Disabled by default; when enabled, validate proxy chain
3. **Rate limiting**: Prevents DoS on search endpoints
4. **No mutations**: Read-only API limits attack surface
5. **API key timing**: Uses `secrets.compare_digest()` for constant-time comparison

---

## 10. Future Considerations

### 10.1 Potential v2 Additions

- `POST /api/v1/workspaces/{id}/reindex` - Trigger re-indexing
- `GET /api/v1/workspaces/{id}/stats` - Index statistics
- `WebSocket /api/v1/workspaces/{id}/watch` - Real-time index updates
- True cursor pagination with keyset queries

### 10.2 OpenAPI Spec

Generate OpenAPI 3.0 spec automatically from route definitions for:
- Client SDK generation
- Interactive documentation (Swagger UI)
- Contract testing

---

## Flagged for Human Decision

1. **Rate limit values**: 60 RPM is a starting point. May need tuning based on real usage patterns.
2. **Workspace auto-discovery**: Should we scan for `.rag/` directories, or require explicit config?
3. **API versioning strategy**: Currently `/api/v1/`. When do we introduce `/api/v2/`?

---

## Confidence Assessment

- **Architecture:** HIGH — Clean separation via sub-app mounting; proven Starlette patterns
- **Feasibility:** HIGH — All components exist; this is integration work, not R&D
- **Risk Level:** LOW — Read-only API, additive changes, feature-flagged

**Overall Recommendation:** PROCEED

The design is sound, addresses all critic concerns, and can be implemented incrementally. The honest acknowledgment of v1 limitations (fake pagination) sets appropriate expectations.
