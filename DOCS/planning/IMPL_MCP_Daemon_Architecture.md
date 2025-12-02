# Implementation Plan: MCP Daemon with Network Transport

**Feature Branch:** `feature/mcp-daemon-architecture`  
**Based on SDD:** `SDD_MCP_Daemon_Architecture.md`  
**Start Date:** 2025-12-02  
**Status:** 🟢 In Progress  

---

## Objectives

Transform LLMC MCP server from stdio-only (Claude Desktop) to a proper network daemon supporting HTTP/SSE transport for external system integration.

**Success Criteria:**
- ✅ HTTP/SSE transport working alongside stdio
- ✅ API key authentication functional
- ✅ Daemon lifecycle management (start/stop/status)
- ✅ CLI tool (`llmc-mcp`) working  
- ✅ Backward compatible with Claude Desktop
- ✅ External clients can connect
- ✅ Tests passing

---

## Implementation Phases

### Phase 1: HTTP Transport Foundation ⏳
**Effort:** 4-6 hours  
**Status:** Starting  
**Difficulty:** 🟡 Medium

#### 1.1 Create transport module structure
- [ ] Create `llmc_mcp/transport/` package
- [ ] Create `llmc_mcp/transport/__init__.py`
- [ ] Create `llmc_mcp/transport/http_server.py`
- [ ] Create `llmc_mcp/transport/auth.py`

#### 1.2 Implement HTTP server with SSE
- [ ] Create `MCPHttpServer` class in `http_server.py`
- [ ] Integrate MCP SDK's `SseServerTransport`
- [ ] Add `/health` endpoint (public)
- [ ] Add `/sse` endpoint (SSE connection)
- [ ] Add `/messages/` mount for JSON-RPC
- [ ] Wire up to existing `LlmcMcpServer`

#### 1.3 Add configuration support
- [ ] Extend `llmc.toml` with `[mcp.http]` section
- [ ] Update config loading in `llmc_mcp/config.py`
- [ ] Add host/port/api_key config options

---

### Phase 2: Authentication ⏳
**Effort:** 2-3 hours  
**Status:** Pending  
**Difficulty:** 🟢 Easy

#### 2.1 API key middleware
- [ ] Implement `APIKeyMiddleware` in `auth.py`
- [ ] Support X-API-Key header
- [ ] Support api_key query parameter
- [ ] Auto-generate key if missing
- [ ] Save to `~/.llmc/mcp-api-key` with 0600 perms

#### 2.2 Key management
- [ ] Implement key file creation
- [ ] Implement key loading from env/file/config
- [ ] Add key display utility

---

### Phase 3: Daemon Management ⏳
**Effort:** 3-4 hours  
**Status:** Pending  
**Difficulty:** 🟡 Medium

#### 3.1 Daemon infrastructure
- [ ] Create `llmc_mcp/daemon.py`
- [ ] Implement `MCPDaemon` class
- [ ] Add double-fork daemonization
- [ ] Implement pidfile management
- [ ] Add signal handlers (SIGTERM, SIGINT)

#### 3.2 Lifecycle operations
- [ ] Implement `start()` method (daemon + foreground modes)
- [ ] Implement `stop()` method
- [ ] Implement `status()` method
- [ ] Implement `restart()` method
- [ ] Add log rotation support

---

### Phase 4: CLI Wrapper ⏳
**Effort:** 2-3 hours  
**Status:** Pending  
**Difficulty:** 🟢 Easy

#### 4.1 Create CLI commands
- [ ] Create `llmc_mcp/cli.py`
- [ ] Implement `llmc-mcp start` command
- [ ] Implement `llmc-mcp stop` command
- [ ] Implement `llmc-mcp restart` command
- [ ] Implement `llmc-mcp status` command
- [ ] Implement `llmc-mcp logs` command
- [ ] Implement `llmc-mcp health` command
- [ ] Implement `llmc-mcp show-key` command

#### 4.2 Add entry point
- [ ] Add `llmc-mcp` script to pyproject.toml
- [ ] Test CLI installation

---

### Phase 5: Testing & Integration ⏳
**Effort:** 2-3 hours  
**Status:** Pending  
**Difficulty:** 🟢 Easy

#### 5.1 Unit tests
- [ ] Test auth middleware
- [ ] Test daemon lifecycle
- [ ] Test pidfile management
- [ ] Test key generation

#### 5.2 Integration tests
- [ ] Test HTTP server starts
- [ ] Test SSE connection
- [ ] Test tool invocation via HTTP
- [ ] Test authentication flow

#### 5.3 Client testing
- [ ] Create example Python client
- [ ] Test with MCP Inspector
- [ ] Verify Claude Desktop still works (stdio)

---

### Phase 6: Documentation & Polish ⏳
**Effort:** 2-3 hours  
**Status:** Pending  
**Difficulty:** 🟢 Easy

#### 6.1 Documentation
- [ ] Create usage guide for HTTP mode
- [ ] Document configuration options
- [ ] Add client connection examples
- [ ] Update README
- [ ] Update CHANGELOG

#### 6.2 Examples
- [ ] Python client example
- [ ] curl examples
- [ ] MCP Inspector example

---

## File Structure

```
llmc_mcp/
├── __init__.py                   # Existing
├── server.py                     # Existing (unchanged)
├── config.py                     # UPDATE: add HTTP config
├── cli.py                        # NEW: CLI commands
├── daemon.py                     # NEW: Daemon manager
├── transport/
│   ├── __init__.py               # NEW
│   ├── http_server.py            # NEW: Starlette app + SSE
│   └── auth.py                   # NEW: API key middleware
└── tools/                        # Existing (unchanged)

tests/
└── test_mcp_daemon.py            # NEW: Integration tests
```

---

## Configuration Example

```toml
[mcp]
enabled = true
log_level = "info"

[mcp.http]
enabled = true
host = "127.0.0.1"        # localhost only (secure default)
port = 8765
api_key_file = "~/.llmc/mcp-api-key"  # auto-generated

[mcp.http.cors]
allowed_origins = ["http://localhost:*"]
allow_credentials = true
```

---

## Dependencies

**New packages needed:**
```toml
[project.optional-dependencies]
daemon = [
    "uvicorn>=0.30.0",      # ASGI server
    "typer>=0.12.0",        # CLI framework
    "rich>=13.0.0",         # Pretty CLI output
]
```

Note: Starlette and sse-starlette already included in MCP SDK.

---

## Usage Examples

### Start Daemon
```bash
llmc-mcp start              # Background daemon
llmc-mcp start --foreground # Run in foreground
llmc-mcp start --port 9000  # Custom port
```

### Manage Daemon
```bash
llmc-mcp status    # Check if running
llmc-mcp stop      # Stop daemon
llmc-mcp restart   # Restart
llmc-mcp logs -f   # Follow logs
```

### Connect from Python
```python
from mcp import ClientSession
from mcp.client.sse import sse_client

async def connect():
    api_key = open("~/.llmc/mcp-api-key").read().strip()
    
    async with sse_client(
        url="http://localhost:8765/sse",
        headers={"X-API-Key": api_key}
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("rag_search", {"query": "test"})
```

---

## Backward Compatibility

**Zero breaking changes:**
- Stdio mode (Claude Desktop) unchanged
- Existing configs work as-is
- HTTP mode is additive, opt-in

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Port conflicts | Default 8765, configurable, check before bind |
| Daemon not stopping | Robust signal handling, timeout on stop |
| Stale pidfiles | Check process exists before trusting pidfile |
| Permission errors | Clear error messages, 0600 on sensitive files |
| API key leaks | File permissions, docs warn against committing |

---

## Timeline

**Target:** 15-22 hours (2-3 focused sessions)

**Critical Path:**
1. HTTP transport (4-6h)
2. Auth (2-3h)
3. Daemon (3-4h)
4. CLI (2-3h)
5. Testing (2-3h)
6. Docs (2-3h)

---

## Exit Criteria

- [ ] HTTP/SSE transport functional
- [ ] Auth middleware working
- [ ] Daemon lifecycle stable
- [ ] CLI commands working
- [ ] Tests passing
- [ ] Documentation complete
- [ ] Claude Desktop still works (stdio mode)
- [ ] External client can connect and invoke tools

---

## Notes

- MCP SDK already has SSE transport - just need to integrate
- Focus on localhost security by default
- Defer TLS/OAuth/multi-instance to P2
- Keep stdio mode completely unchanged
