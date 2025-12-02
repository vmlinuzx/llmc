# SDD: MCP Daemon with Network Transport (Roadmap 1.7 - Revised)

**Author:** Otto (Claude Opus 4.5)  
**Date:** 2025-12-02  
**Status:** Architecture Review  
**Supersedes:** SDD_MCP_CLI_Wrapper.md (incorrect problem framing)

---

## Executive Summary

The original roadmap item 1.7 asked for a "CLI wrapper" but the actual need is **network transport** - the ability for external systems to connect to LLMC's MCP server over TCP/HTTP. The existing stdio transport only works when Claude Desktop spawns the process directly.

**What we actually need:**
1. Add HTTP/SSE transport layer alongside existing stdio
2. Run the MCP server as a proper network daemon
3. CLI tooling (`llmc-mcp`) to manage the daemon lifecycle
4. Authentication to secure the HTTP endpoint

**Good news:** The MCP Python SDK already includes `SseServerTransport` and `StreamableHTTPTransport` - we just need to integrate them.

---

## 1. Problem Statement

### Current Architecture
```
Claude Desktop ──spawns──▶ python -m llmc_mcp.server ──stdio──▶ MCP protocol
                              │
                              └─▶ No network interface
                              └─▶ Single client only
                              └─▶ Dies when Claude Desktop closes
```

### What External Systems Need
```
┌──────────────────┐     HTTP/SSE      ┌─────────────────────┐
│ Codex/OpenAI     │◀─────────────────▶│                     │
├──────────────────┤                   │   LLMC MCP Daemon   │
│ Gemini agents    │◀─────────────────▶│   (port 8765)       │
├──────────────────┤                   │                     │
│ Custom scripts   │◀─────────────────▶│                     │
├──────────────────┤                   └─────────────────────┘
│ Other MCPs       │◀──────────────────────────▲
└──────────────────┘                           │
                                               │ stdio (unchanged)
                                   ┌───────────┴───────────┐
                                   │   Claude Desktop      │
                                   └───────────────────────┘
```

### Pain Points Addressed
| Pain Point | Solution |
|------------|----------|
| Can't connect from external agents | HTTP/SSE transport on TCP port |
| Server dies with Claude Desktop | Daemon mode with systemd |
| No multi-client support | Stateful session management |
| No auth = security risk | API key validation middleware |
| No management tooling | `llmc-mcp` CLI with start/stop/status |

---

## 2. Architecture

### 2.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LLMC MCP Daemon                                 │
│                                                                         │
│   ┌───────────────────────────────────────────────────────────────┐     │
│   │                    Transport Layer                            │     │
│   │                                                               │     │
│   │  ┌─────────────┐    ┌─────────────────────────────────────┐   │     │
│   │  │   stdio     │    │     HTTP Server (Starlette)         │   │     │
│   │  │  adapter    │    │                                     │   │     │
│   │  │             │    │  /health   → liveness probe         │   │     │
│   │  │  (existing) │    │  /sse      → SSE connection (GET)   │   │     │
│   │  │             │    │  /messages → JSON-RPC (POST)        │   │     │
│   │  └──────┬──────┘    └──────────────┬──────────────────────┘   │     │
│   │         │                          │                          │     │
│   └─────────┼──────────────────────────┼──────────────────────────┘     │
│             │                          │                                │
│             │         ┌────────────────┴────────────────┐               │
│             │         │     Auth Middleware             │               │
│             │         │  (API key validation)           │               │
│             │         └────────────────┬────────────────┘               │
│             │                          │                                │
│             └──────────────┬───────────┘                                │
│                            │                                            │
│                    ┌───────┴───────┐                                    │
│                    │  MCP Server   │                                    │
│                    │  (existing    │                                    │
│                    │   LlmcMcp     │                                    │
│                    │   Server)     │                                    │
│                    └───────┬───────┘                                    │
│                            │                                            │
│                    ┌───────┴───────┐                                    │
│                    │  LLMC Tools   │                                    │
│                    │ (47 tools)    │                                    │
│                    └───────────────┘                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Components

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| **Transport Layer** | Abstract over stdio vs HTTP | New: `transport.py` |
| **HTTP Server** | Starlette ASGI app with routes | New: `http_server.py` |
| **Auth Middleware** | API key validation | New: `auth.py` |
| **Session Manager** | Track active SSE connections | Built into MCP SDK |
| **MCP Server** | Existing tool handlers | Existing: `server.py` |
| **Daemon Manager** | Pidfile, signals, lifecycle | New: `daemon.py` |
| **CLI** | User-facing commands | New: `cli.py` |

### 2.3 Transport Modes

The daemon supports two transport modes, selectable at startup:

```python
class TransportMode(Enum):
    STDIO = "stdio"       # Existing behavior (Claude Desktop)
    HTTP = "http"         # New network daemon mode
    BOTH = "both"         # Future: multiplex (P2)
```

**stdio mode** (default, existing):
- Launched by Claude Desktop via `python -m llmc_mcp.server`
- Communicates via stdin/stdout pipes
- Single client, dies when parent exits

**HTTP mode** (new):
- Launched by `llmc-mcp start`  
- Listens on configurable port (default: 8765)
- Multiple concurrent clients via SSE sessions
- Runs as daemon with pidfile

---

## 3. Implementation Plan

### Phase 1: HTTP Transport (P0, 4-6 hours)

**Goal:** Get the MCP server responding over HTTP/SSE.

**Files to create:**
```
llmc_mcp/
├── transport/
│   ├── __init__.py
│   ├── http_server.py    # Starlette app with SSE routes
│   └── auth.py           # API key middleware
```

**http_server.py sketch:**
```python
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import Response, JSONResponse
from mcp.server.sse import SseServerTransport
import uvicorn

class MCPHttpServer:
    """HTTP server that exposes MCP over SSE transport."""
    
    def __init__(self, mcp_server: LlmcMcpServer, config: ServerConfig):
        self.mcp_server = mcp_server
        self.config = config
        self.sse_transport = SseServerTransport("/messages/")
        self.app = self._create_app()
    
    def _create_app(self) -> Starlette:
        routes = [
            Route("/health", endpoint=self._health, methods=["GET"]),
            Route("/sse", endpoint=self._handle_sse, methods=["GET"]),
            Mount("/messages/", app=self.sse_transport.handle_post_message),
        ]
        return Starlette(routes=routes, on_startup=[self._on_startup])
    
    async def _health(self, request):
        return JSONResponse({"status": "ok", "tools": len(self.mcp_server.tools)})
    
    async def _handle_sse(self, request):
        """Handle SSE connection - this is where MCP runs."""
        async with self.sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await self.mcp_server.server.run(
                read_stream,
                write_stream,
                self.mcp_server.server.create_initialization_options(),
            )
        return Response()
    
    def run(self, host: str = "127.0.0.1", port: int = 8765):
        uvicorn.run(self.app, host=host, port=port)
```


### Phase 2: Authentication (P0, 2-3 hours)

**Goal:** Secure the HTTP endpoint with API key validation.

**auth.py sketch:**
```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import secrets
import os

class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate API key in X-API-Key header or query param."""
    
    def __init__(self, app, api_key: str | None = None):
        super().__init__(app)
        # Load from env, config, or generate
        self.api_key = api_key or os.getenv("LLMC_MCP_API_KEY") or self._generate_key()
    
    async def dispatch(self, request, call_next):
        # Health endpoint is public
        if request.url.path == "/health":
            return await call_next(request)
        
        # Check header or query param
        provided_key = (
            request.headers.get("X-API-Key") or 
            request.query_params.get("api_key")
        )
        
        if not secrets.compare_digest(provided_key or "", self.api_key):
            return JSONResponse(
                {"error": "Invalid or missing API key"},
                status_code=401
            )
        
        return await call_next(request)
    
    def _generate_key(self) -> str:
        """Generate and persist a new API key."""
        key = secrets.token_urlsafe(32)
        # Save to ~/.llmc/mcp-api-key
        key_path = Path.home() / ".llmc" / "mcp-api-key"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(key)
        key_path.chmod(0o600)
        return key
```

**Config additions to llmc.toml:**
```toml
[mcp.http]
enabled = true
host = "127.0.0.1"      # localhost only by default
port = 8765
api_key_file = "~/.llmc/mcp-api-key"  # auto-generated if missing
```

### Phase 3: Daemon Management (P0, 3-4 hours)

**Goal:** Proper daemonization with pidfile and signal handling.

**daemon.py sketch:**
```python
import os
import sys
import signal
import atexit
from pathlib import Path

class MCPDaemon:
    """Daemon process manager for LLMC MCP server."""
    
    PIDFILE = Path.home() / ".llmc" / "mcp-daemon.pid"
    LOGFILE = Path.home() / ".llmc" / "logs" / "mcp-daemon.log"
    
    def __init__(self, server_factory: Callable[[], MCPHttpServer]):
        self.server_factory = server_factory
        self._server = None
    
    def start(self, foreground: bool = False):
        """Start the daemon (daemonize unless foreground=True)."""
        if self._is_running():
            print(f"Daemon already running (PID {self._get_pid()})")
            return False
        
        if not foreground:
            self._daemonize()
        
        self._write_pidfile()
        atexit.register(self._cleanup)
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        
        self._server = self.server_factory()
        self._server.run()
    
    def stop(self):
        """Stop the running daemon."""
        pid = self._get_pid()
        if not pid:
            print("Daemon not running")
            return False
        
        os.kill(pid, signal.SIGTERM)
        self.PIDFILE.unlink(missing_ok=True)
        return True
    
    def status(self) -> dict:
        """Get daemon status."""
        pid = self._get_pid()
        running = self._is_running()
        return {
            "running": running,
            "pid": pid if running else None,
            "pidfile": str(self.PIDFILE),
            "logfile": str(self.LOGFILE),
        }
    
    def _daemonize(self):
        """Double-fork to detach from terminal."""
        # First fork
        if os.fork() > 0:
            sys.exit(0)
        
        os.setsid()
        
        # Second fork
        if os.fork() > 0:
            sys.exit(0)
        
        # Redirect std streams
        sys.stdout.flush()
        sys.stderr.flush()
        with open('/dev/null', 'r') as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())
        with open(self.LOGFILE, 'a') as log:
            os.dup2(log.fileno(), sys.stdout.fileno())
            os.dup2(log.fileno(), sys.stderr.fileno())
    
    def _is_running(self) -> bool:
        """Check if daemon is actually running."""
        pid = self._get_pid()
        if not pid:
            return False
        try:
            os.kill(pid, 0)  # Check if process exists
            return True
        except OSError:
            return False
    
    def _get_pid(self) -> int | None:
        """Read PID from pidfile."""
        try:
            return int(self.PIDFILE.read_text().strip())
        except (FileNotFoundError, ValueError):
            return None
    
    def _write_pidfile(self):
        self.PIDFILE.parent.mkdir(parents=True, exist_ok=True)
        self.PIDFILE.write_text(str(os.getpid()))
    
    def _cleanup(self):
        self.PIDFILE.unlink(missing_ok=True)
    
    def _handle_signal(self, signum, frame):
        self._cleanup()
        sys.exit(0)
```


### Phase 4: CLI Wrapper (P0, 2-3 hours)

**Goal:** User-friendly `llmc-mcp` command.

**cli.py sketch:**
```python
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="LLMC MCP Server management")
console = Console()

@app.command()
def start(
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground"),
    port: int = typer.Option(8765, "--port", "-p", help="HTTP port"),
    host: str = typer.Option("127.0.0.1", "--host", "-H", help="Bind address"),
):
    """Start the MCP daemon."""
    from llmc_mcp.daemon import MCPDaemon
    from llmc_mcp.transport.http_server import MCPHttpServer
    from llmc_mcp.server import LlmcMcpServer
    from llmc_mcp.config import load_config
    
    config = load_config()
    
    def server_factory():
        mcp_server = LlmcMcpServer(config)
        return MCPHttpServer(mcp_server, host=host, port=port)
    
    daemon = MCPDaemon(server_factory)
    
    if daemon.start(foreground=foreground):
        if foreground:
            console.print(f"[green]✓[/] MCP server running on http://{host}:{port}")
        else:
            console.print(f"[green]✓[/] MCP daemon started (PID {daemon._get_pid()})")
            console.print(f"  Listening: http://{host}:{port}")
            console.print(f"  Logs: {daemon.LOGFILE}")

@app.command()
def stop():
    """Stop the MCP daemon."""
    from llmc_mcp.daemon import MCPDaemon
    daemon = MCPDaemon(lambda: None)
    
    if daemon.stop():
        console.print("[green]✓[/] MCP daemon stopped")
    else:
        console.print("[yellow]![/] Daemon was not running")

@app.command()
def status():
    """Show daemon status."""
    from llmc_mcp.daemon import MCPDaemon
    daemon = MCPDaemon(lambda: None)
    info = daemon.status()
    
    if info["running"]:
        console.print(f"[green]●[/] MCP daemon is [bold]running[/] (PID {info['pid']})")
    else:
        console.print("[red]●[/] MCP daemon is [bold]stopped[/]")
    
    console.print(f"  Pidfile: {info['pidfile']}")
    console.print(f"  Logfile: {info['logfile']}")

@app.command()
def logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
):
    """Show daemon logs."""
    from llmc_mcp.daemon import MCPDaemon
    import subprocess
    
    daemon = MCPDaemon(lambda: None)
    logfile = daemon.LOGFILE
    
    if not logfile.exists():
        console.print("[yellow]No logs found yet[/]")
        return
    
    if follow:
        subprocess.run(["tail", "-f", str(logfile)])
    else:
        subprocess.run(["tail", "-n", str(lines), str(logfile)])

@app.command()
def health():
    """Quick health check (for scripts)."""
    import httpx
    from llmc_mcp.daemon import MCPDaemon
    
    daemon = MCPDaemon(lambda: None)
    if not daemon._is_running():
        raise SystemExit(1)
    
    # TODO: read port from config
    try:
        r = httpx.get("http://127.0.0.1:8765/health", timeout=5)
        if r.status_code == 200:
            raise SystemExit(0)
    except Exception:
        pass
    raise SystemExit(1)

@app.command()
def show_key():
    """Display the API key for connecting to the daemon."""
    from pathlib import Path
    key_path = Path.home() / ".llmc" / "mcp-api-key"
    if key_path.exists():
        console.print(f"API Key: [bold]{key_path.read_text().strip()}[/]")
    else:
        console.print("[yellow]No API key generated yet. Start the daemon first.[/]")

if __name__ == "__main__":
    app()
```

**Entry point in pyproject.toml:**
```toml
[project.scripts]
llmc-mcp = "llmc_mcp.cli:app"
```


### Phase 5: Integration & Testing (P1, 2-3 hours)

- Unit tests for auth middleware
- Integration test: start daemon → connect via MCP client → call tool
- Smoke test script for CI
- Update Claude Desktop config example to show both modes

---

## 4. Configuration

### 4.1 llmc.toml additions

```toml
[mcp]
enabled = true
log_level = "info"

[mcp.http]
# HTTP daemon mode settings
enabled = true
host = "127.0.0.1"        # Bind to localhost only (secure default)
port = 8765               # MCP daemon port
api_key_file = "~/.llmc/mcp-api-key"  # Auto-generated if missing
# api_key = "..."         # Or specify directly (not recommended)

[mcp.http.cors]
# CORS settings for browser-based clients
allowed_origins = ["http://localhost:*"]
allow_credentials = true

[mcp.http.tls]
# TLS settings (optional, recommended for non-localhost)
enabled = false
cert_file = ""
key_file = ""
```

### 4.2 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLMC_MCP_API_KEY` | Override API key | Auto-generated |
| `LLMC_MCP_PORT` | Override port | 8765 |
| `LLMC_MCP_HOST` | Override bind address | 127.0.0.1 |

---

## 5. Client Usage

### 5.1 Connecting from Python

```python
from mcp import ClientSession
from mcp.client.sse import sse_client

async def connect_to_llmc():
    api_key = "your-api-key"
    
    async with sse_client(
        url="http://localhost:8765/sse",
        headers={"X-API-Key": api_key}
    ) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize
            await session.initialize()
            
            # List tools
            tools = await session.list_tools()
            print(f"Available: {len(tools.tools)} tools")
            
            # Call a tool
            result = await session.call_tool("rag_search", {"query": "config"})
            print(result)
```

### 5.2 Connecting from curl (debugging)

```bash
# Get API key
API_KEY=$(cat ~/.llmc/mcp-api-key)

# Health check
curl http://localhost:8765/health

# SSE connection (will stream events)
curl -N -H "X-API-Key: $API_KEY" http://localhost:8765/sse
```

### 5.3 MCP Inspector

The MCP Inspector tool can connect directly:
```bash
npx @anthropic/mcp-inspector --url http://localhost:8765/sse \
    --header "X-API-Key: $(cat ~/.llmc/mcp-api-key)"
```

---

## 6. Migration Guide

### For Claude Desktop Users

**No changes required.** The existing stdio transport continues to work exactly as before. Claude Desktop config remains:

```json
{
  "mcpServers": {
    "llmc": {
      "command": "python",
      "args": ["-m", "llmc_mcp.server"],
      "cwd": "/home/user/src/llmc"
    }
  }
}
```

### For External System Integration

Start the daemon, then connect:

```bash
# Start daemon
llmc-mcp start

# Get your API key
llmc-mcp show-key

# Configure your external system with:
#   URL: http://localhost:8765/sse
#   API Key: (from above)
```

---

## 7. Security Considerations

| Risk | Mitigation |
|------|------------|
| Unauthorized access | API key required for all endpoints except /health |
| Key exposure | Key file has 0600 permissions; use env var for CI |
| Network exposure | Binds to localhost by default; explicit opt-in for 0.0.0.0 |
| MITM attacks | TLS support available for production deployments |
| DNS rebinding | MCP SDK includes built-in DNS rebinding protection |

### Production Checklist

- [ ] Use TLS in production (`mcp.http.tls.enabled = true`)
- [ ] Bind to specific interface, not `0.0.0.0`
- [ ] Rotate API keys periodically
- [ ] Set up firewall rules for the daemon port
- [ ] Use systemd socket activation for privilege separation

---

## 8. Future Work (P2+)

### 8.1 Multiplexed Mode
Run both stdio (for Claude Desktop) and HTTP simultaneously from a single daemon.

### 8.2 Systemd Integration
- Socket activation for on-demand startup
- Service unit file for managed deployments
- Journal integration for logs

### 8.3 Remote Access
- OAuth2 authentication for multi-user deployments
- Rate limiting per client
- Usage quotas

### 8.4 Multi-Instance
- Run multiple daemon instances with different configs
- Named instances: `llmc-mcp start --name prod`
- Per-instance pidfiles and logs

---

## 9. Implementation Timeline

| Phase | Effort | Difficulty | Dependencies | Deliverables |
|-------|--------|------------|--------------|--------------|
| **Phase 1: HTTP + SSE Transport** | 4-6h | 🟡 Medium | MCP SDK | `http_server.py`, SSE endpoints working |
| **Phase 2: WebSocket Transport** | 2-3h | 🟢 Easy | Phase 1 | `websocket.py`, WS endpoint (SDK has it) |
| **Phase 3: Auth Middleware** | 2-3h | 🟢 Easy | Phase 1 | `auth.py`, API key validation |
| **Phase 4: Daemon Manager** | 3-4h | 🟡 Medium | Phase 1-3 | `daemon.py`, pidfile, signals, double-fork |
| **Phase 5: CLI Wrapper** | 2-3h | 🟢 Easy | Phase 4 | `cli.py`, `llmc-mcp` command |
| **Phase 6: Testing & Docs** | 2-3h | 🟢 Easy | All | Tests, examples, CI integration |

**Difficulty Key:**
- 🟢 **Easy** - Straightforward implementation, SDK does heavy lifting
- 🟡 **Medium** - Some complexity, requires careful design
- 🔴 **Hard** - Significant complexity, edge cases, debugging expected

**Total: 15-22 hours** (~2-3 focused sessions)

---

## 10. Design Decisions

### Confirmed
1. **WebSocket transport:** Yes, include alongside SSE. Some clients prefer it.
2. **Bind address:** Default to `127.0.0.1` (localhost only). External access is opt-in via config.

### Open Questions

1. **API key rotation strategy?** Should `llmc-mcp rotate-key` be a command?

2. **Config hot-reload?** Should SIGHUP reload config without restart?

3. **Metrics endpoint?** Add `/metrics` for Prometheus scraping?

---

## Appendix A: File Structure After Implementation

```
llmc_mcp/
├── __init__.py
├── server.py              # Existing MCP server (unchanged)
├── config.py              # Extended with http config
├── cli.py                 # NEW: llmc-mcp CLI
├── daemon.py              # NEW: Daemon management
├── transport/
│   ├── __init__.py
│   ├── http_server.py     # NEW: Starlette app
│   └── auth.py            # NEW: API key middleware
├── tools/                 # Existing tools (unchanged)
└── ...
```

## Appendix B: Dependencies

New dependencies required:
```toml
[project.optional-dependencies]
daemon = [
    "uvicorn>=0.30.0",      # ASGI server
    "starlette>=0.38.0",    # Already required by MCP SDK
    "sse-starlette>=2.0.0", # Already required by MCP SDK
    "typer>=0.12.0",        # CLI framework
    "rich>=13.0.0",         # Pretty output
]
```

The core MCP SDK already includes Starlette and sse-starlette, so the only truly new deps are uvicorn, typer, and rich.
