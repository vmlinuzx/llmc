#!/usr/bin/env python3
"""
LLMC MCP Server - Model Context Protocol interface for LLMC RAG system.

Supports stdio transport for Claude Desktop integration.
Run with: python -m llmc_mcp.server

M0-M3 Tools:
- health: Server status check
- rag_search: RAG index queries (direct adapter)
- read_file: Safe file reading
- list_dir: Directory listing
- stat: File/dir metadata
- run_cmd: Command execution with allowlist (M3)
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from llmc_mcp.config import McpConfig, load_config
from llmc_mcp.observability import ObservabilityContext, setup_logging

# Configure logging to stderr (Claude Desktop captures it)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("llmc-mcp")

# Tool definitions for list_tools
TOOLS: list[Tool] = [
    Tool(
        name="health",
        description="Check LLMC MCP server health and version",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="list_tools",
        description="List all available tools and their schemas.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="rag_search",
        description="Search LLMC RAG index for relevant code/docs. Returns ranked snippets with provenance.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query or code concept to search for",
                },
                "scope": {
                    "type": "string",
                    "enum": ["repo", "docs", "both"],
                    "description": "Search scope: repo (code), docs, or both",
                    "default": "repo",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (1-20)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="read_file",
        description="Read contents of a file. Returns text content with metadata.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to file",
                },
                "max_bytes": {
                    "type": "integer",
                    "description": "Maximum bytes to read (default 1MB)",
                    "default": 1048576,
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="list_dir",
        description="List contents of a directory. Returns files and subdirectories.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to directory",
                },
                "max_entries": {
                    "type": "integer",
                    "description": "Maximum entries to return (default 1000)",
                    "default": 1000,
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Include hidden files (starting with .)",
                    "default": False,
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="stat",
        description="Get file or directory metadata (size, timestamps, permissions).",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path",
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="run_cmd",
        description="Execute a shell command with allowlist validation and timeout. Only approved binaries can run.",
        inputSchema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute (first word must be in allowlist)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max execution time in seconds (default 30)",
                    "default": 30,
                },
            },
            "required": ["command"],
        },
    ),
    Tool(
        name="get_metrics",
        description="Get MCP server metrics (call counts, latencies, errors). Requires observability enabled.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]


class LlmcMcpServer:
    """LLMC MCP Server implementation."""
    
    def __init__(self, config: McpConfig):
        self.config = config
        self.server = Server("llmc-mcp")
        
        # Initialize observability (M4)
        self.obs = ObservabilityContext(config.observability)
        
        self.tool_handlers = {
            "health": self._handle_health,
            "list_tools": self._handle_list_tools,
            "rag_search": self._handle_rag_search,
            "read_file": self._handle_read_file,
            "list_dir": self._handle_list_dir,
            "stat": self._handle_stat,
            "run_cmd": self._handle_run_cmd,
            "get_metrics": self._handle_get_metrics,
        }
        
        self._register_handlers()
        logger.info(f"LLMC MCP Server initialized ({config.config_version})")
    
    def _register_handlers(self):
        """Register MCP protocol handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """Return available tools."""
            logger.debug("list_tools called")
            return TOOLS
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool invocation with observability."""
            cid = self.obs.correlation_id()
            start_time = time.time()
            success = True
            error_msg = None
            
            logger.info(f"call_tool: {name}", extra={"correlation_id": cid, "tool": name})
            
            try:
                handler = self.tool_handlers.get(name)
                if handler:
                    # Handle args being optional for some handlers
                    import inspect
                    sig = inspect.signature(handler)
                    if "args" in sig.parameters:
                        result = await handler(arguments)
                    else:
                        result = await handler()
                else:
                    success = False
                    error_msg = f"Unknown tool: {name}"
                    result = [TextContent(
                        type="text",
                        text=f'{{"error": "{error_msg}"}}',
                    )]
                
                # Check for error in result (soft failure)
                if result and '"error"' in result[0].text:
                    success = False
                    # Try to extract error message for logging
                    try:
                        import json
                        data = json.loads(result[0].text)
                        if "error" in data:
                            error_msg = data["error"]
                    except:
                        pass
                    
            except Exception as e:
                success = False
                error_msg = str(e)
                logger.exception(f"Tool {name} failed: {e}", extra={"correlation_id": cid, "tool": name})
                result = [TextContent(
                    type="text",
                    text=f'{{"error": "{str(e)}"}}',
                )]
            
            # Record metrics
            latency_ms = (time.time() - start_time) * 1000
            self.obs.record(
                correlation_id=cid,
                tool=name,
                latency_ms=latency_ms,
                success=success,
                # Token estimation: rough chars/4 heuristic
                tokens_in=len(str(arguments)) // 4,
                tokens_out=len(result[0].text) // 4 if result else 0,
            )
            
            logger.info(
                f"call_tool done: {name}",
                extra={
                    "correlation_id": cid,
                    "tool": name,
                    "latency_ms": latency_ms,
                    "status": "ok" if success else "error",
                    "error": error_msg
                }
            )
            
            return result
    
    async def _handle_health(self) -> list[TextContent]:
        """Health check handler."""
        import json
        result = {
            "ok": True,
            "version": self.config.config_version,
            "server": "llmc-mcp",
            "transport": self.config.server.transport,
            "rag_enabled": self.config.rag.jit_context_enabled,
            "run_cmd_enabled": self.config.tools.enable_run_cmd,
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    async def _handle_list_tools(self) -> list[TextContent]:
        """List tools handler."""
        import json
        # TOOLS is global
        data = [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.inputSchema
            } 
            for t in TOOLS
        ]
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    async def _handle_get_metrics(self) -> list[TextContent]:
        """Get server metrics handler."""
        import json
        
        if not self.obs.enabled:
            return [TextContent(
                type="text",
                text='{"error": "Observability disabled in config (mcp.observability.enabled = false)"}',
            )]
        
        stats = self.obs.get_stats()
        return [TextContent(type="text", text=json.dumps(stats, indent=2))]
    
    async def _handle_rag_search(self, args: dict) -> list[TextContent]:
        """RAG search handler - direct adapter (no subprocess)."""
        import json
        from llmc_mcp.tools.rag import rag_search
        
        query = args.get("query", "")
        scope = args.get("scope", self.config.rag.default_scope)
        limit = min(args.get("limit", 5), self.config.rag.top_k * 2)
        
        if not query:
            return [TextContent(type="text", text='{"error": "query is required"}')]
        
        # Find LLMC root from config
        llmc_root = Path(self.config.tools.allowed_roots[0]) if self.config.tools.allowed_roots else Path(".")
        
        # Direct call - no subprocess overhead
        result = rag_search(
            query=query,
            repo_root=llmc_root,
            limit=limit,
            scope=scope,
        )
        
        if result.error:
            return [TextContent(
                type="text",
                text=json.dumps({"error": result.error}),
            )]
        
        # Return normalized structure (data + meta)
        return [TextContent(type="text", text=json.dumps(result.to_dict(), indent=2))]
    
    async def _handle_read_file(self, args: dict) -> list[TextContent]:
        """Read file handler."""
        import json
        from llmc_mcp.tools.fs import read_file
        
        path = args.get("path", "")
        max_bytes = args.get("max_bytes", 1_048_576)
        
        if not path:
            return [TextContent(type="text", text='{"error": "path is required"}')]
        
        result = read_file(path, self.config.tools.allowed_roots, max_bytes=max_bytes)
        
        if result.success:
            return [TextContent(
                type="text",
                text=json.dumps({"data": result.data, "meta": result.meta}),
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({"error": result.error, "meta": result.meta}),
            )]
    
    async def _handle_list_dir(self, args: dict) -> list[TextContent]:
        """List directory handler."""
        import json
        from llmc_mcp.tools.fs import list_dir
        
        path = args.get("path", "")
        max_entries = args.get("max_entries", 1000)
        include_hidden = args.get("include_hidden", False)
        
        if not path:
            return [TextContent(type="text", text='{"error": "path is required"}')]
        
        result = list_dir(
            path,
            self.config.tools.allowed_roots,
            max_entries=max_entries,
            include_hidden=include_hidden,
        )
        
        if result.success:
            return [TextContent(
                type="text",
                text=json.dumps({"data": result.data, "meta": result.meta}),
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({"error": result.error, "meta": result.meta}),
            )]
    
    async def _handle_stat(self, args: dict) -> list[TextContent]:
        """Stat path handler."""
        import json
        from llmc_mcp.tools.fs import stat_path
        
        path = args.get("path", "")
        
        if not path:
            return [TextContent(type="text", text='{"error": "path is required"}')]
        
        result = stat_path(path, self.config.tools.allowed_roots)
        
        if result.success:
            return [TextContent(
                type="text",
                text=json.dumps({"data": result.data, "meta": result.meta}),
            )]
        else:
            return [TextContent(
                type="text",
                text=json.dumps({"error": result.error, "meta": result.meta}),
            )]
    
    async def _handle_run_cmd(self, args: dict) -> list[TextContent]:
        """Execute command handler."""
        import json
        from llmc_mcp.tools.cmd import run_cmd
        
        command = args.get("command", "")
        timeout = args.get("timeout", self.config.tools.exec_timeout)
        
        if not command:
            return [TextContent(type="text", text='{"error": "command is required"}')]
        
        if not self.config.tools.enable_run_cmd:
            return [TextContent(
                type="text",
                text='{"error": "run_cmd is disabled in config (mcp.tools.enable_run_cmd = false)"}',
            )]
        
        # Get working directory (first allowed root)
        cwd = Path(self.config.tools.allowed_roots[0]) if self.config.tools.allowed_roots else Path(".")
        
        result = run_cmd(
            command=command,
            cwd=cwd,
            allowlist=self.config.tools.run_cmd_allowlist,
            timeout=min(timeout, self.config.tools.exec_timeout),
        )
        
        response = {
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
        }
        if result.error:
            response["error"] = result.error
            
        return [TextContent(type="text", text=json.dumps(response, indent=2))]
    
    async def run(self):
        """Run the server with stdio transport."""
        logger.info("Starting LLMC MCP server (stdio transport)")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


def main():
    """Entry point for LLMC MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="LLMC MCP Server")
    parser.add_argument(
        "--config", "-c",
        help="Path to llmc.toml config file",
        default=None,
    )
    parser.add_argument(
        "--log-level", "-l",
        choices=["debug", "info", "warning", "error"],
        default=None,
        help="Override log level",
    )
    args = parser.parse_args()
    
    # Load config
    config = load_config(args.config)
    
    # Apply CLI overrides
    if args.log_level:
        config.server.log_level = args.log_level
        config.observability.log_level = args.log_level
    
    # Set up logging (use observability config if enabled)
    global logger
    if config.observability.enabled:
        logger = setup_logging(config.observability, "llmc-mcp")
    else:
        log_level = getattr(logging, config.server.log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(log_level)
        logger.setLevel(log_level)
    
    # Log effective config (minus secrets)
    logger.info(f"Config loaded: enabled={config.enabled}, version={config.config_version}")
    logger.info(f"Tools: allowed_roots={config.tools.allowed_roots}, run_cmd={config.tools.enable_run_cmd}")
    logger.info(f"RAG: scope={config.rag.default_scope}, top_k={config.rag.top_k}")
    logger.info(f"Observability: enabled={config.observability.enabled}, log_format={config.observability.log_format}")
    
    if not config.enabled:
        logger.warning("MCP server disabled in config, exiting")
        sys.exit(0)
    
    # Create and run server
    server = LlmcMcpServer(config)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
