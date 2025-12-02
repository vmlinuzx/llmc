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
"""  # noqa: I001

from __future__ import annotations

import asyncio
from collections.abc import Callable
import inspect
import json
import logging
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Any, cast

from llmc_mcp.config import McpConfig, load_config
from llmc_mcp.observability import ObservabilityContext, setup_logging
from llmc_mcp.prompts import BOOTSTRAP_PROMPT
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Configure logging to stderr (Claude Desktop captures it)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("llmc-mcp")

# Tool definitions for code execution mode
TOOLS: list[Tool] = [
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
    Tool(
        name="te_run",
        description="Execute a shell command through the Tool Envelope (TE) wrapper. Returns structured JSON output.",
        inputSchema={
            "type": "object",
            "properties": {
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command arguments (e.g. ['grep', 'pattern', 'file'])",
                },
                "cwd": {
                    "type": "string",
                    "description": "Optional working directory (must be within allowed roots)",
                },
                "timeout": {
                    "type": "number",
                    "description": "Execution timeout in seconds",
                },
            },
            "required": ["args"],
        },
    ),
    Tool(
        name="repo_read",
        description="Read a file from a repository via the Tool Envelope.",
        inputSchema={
            "type": "object",
            "properties": {
                "root": {
                    "type": "string",
                    "description": "Root path of the repository",
                },
                "path": {
                    "type": "string",
                    "description": "Relative path to the file",
                },
                "max_bytes": {
                    "type": "integer",
                    "description": "Maximum bytes to read (optional)",
                },
            },
            "required": ["root", "path"],
        },
    ),
    Tool(
        name="rag_query",
        description="Query the RAG system via the Tool Envelope.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "k": {
                    "type": "integer",
                    "description": "Number of results to return (default 5)",
                },
                "index": {
                    "type": "string",
                    "description": "Specific index to query (optional)",
                },
                "filters": {
                    "type": "object",
                    "description": "Metadata filters (optional)",
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="rag_search_enriched",
        description="Advanced RAG search with graph-based relationship enrichment. Supports multiple enrichment modes for semantic + relationship-aware retrieval.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query or code concept to search for",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (1-20)",
                    "default": 5,
                },
                "enrich_mode": {
                    "type": "string",
                    "enum": ["vector", "graph", "hybrid", "auto"],
                    "description": "Enrichment strategy: vector (semantic only), graph (relationships), hybrid (both), auto (intelligent routing)",
                    "default": "auto",
                },
                "graph_depth": {
                    "type": "integer",
                    "description": "Relationship traversal depth (0-3). Higher values find more distant relationships",
                    "default": 1,
                },
                "include_features": {
                    "type": "boolean",
                    "description": "Include enrichment quality metrics in response meta",
                    "default": False,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="rag_where_used",
        description="Find where a symbol is used (callers, imports) across the codebase.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name to find usages of",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 50)",
                    "default": 50,
                },
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="rag_lineage",
        description="Trace symbol dependency lineage (upstream/downstream).",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name to trace",
                },
                "direction": {
                    "type": "string",
                    "enum": ["upstream", "downstream", "callers", "callees"],
                    "description": "Trace direction: upstream (what calls this) or downstream (what this calls)",
                    "default": "downstream",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 50)",
                    "default": 50,
                },
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="inspect",
        description="Deep inspection of a file or symbol: snippet, graph relationships, and enrichment data.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path (relative to repo root)",
                },
                "symbol": {
                    "type": "string",
                    "description": "Symbol name (e.g. 'MyClass.method')",
                },
                "include_full_source": {
                    "type": "boolean",
                    "description": "Include full file source code (use sparingly)",
                    "default": False,
                },
                "max_neighbors": {
                    "type": "integer",
                    "description": "Max related entities to return per category",
                    "default": 3,
                },
            },
        },
    ),
    Tool(
        name="rag_stats",
        description="Get statistics about the RAG graph and enrichment coverage.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    # L2 LinuxOps Tools
    Tool(
        name="linux_proc_list",
        description="List running processes with CPU/memory usage. Returns bounded results sorted by CPU.",
        inputSchema={
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Maximum processes to return (1-5000, default 200)",
                    "default": 200,
                },
                "user": {
                    "type": "string",
                    "description": "Optional username filter",
                },
            },
        },
    ),
    Tool(
        name="linux_proc_kill",
        description="Send signal to a process. Safety guards prevent killing PID 1 or MCP server.",
        inputSchema={
            "type": "object",
            "properties": {
                "pid": {
                    "type": "integer",
                    "description": "Process ID to signal",
                },
                "signal": {
                    "type": "string",
                    "enum": ["TERM", "KILL", "INT", "HUP", "STOP", "CONT"],
                    "description": "Signal to send (default TERM)",
                    "default": "TERM",
                },
            },
            "required": ["pid"],
        },
    ),
    Tool(
        name="linux_sys_snapshot",
        description="Get system resource snapshot: CPU, memory, disk usage, and load average.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    # L3 LinuxOps - Interactive REPLs
    Tool(
        name="linux_proc_start",
        description="Start an interactive process/REPL. Returns proc_id for subsequent send/read/stop.",
        inputSchema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to run (e.g. 'python -i', 'bash', 'node')",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (optional)",
                },
                "initial_read_timeout_ms": {
                    "type": "integer",
                    "description": "Time to wait for initial output (default 1000)",
                    "default": 1000,
                },
            },
            "required": ["command"],
        },
    ),
    Tool(
        name="linux_proc_send",
        description="Send input to a managed process. Newline appended automatically.",
        inputSchema={
            "type": "object",
            "properties": {
                "proc_id": {
                    "type": "string",
                    "description": "Process ID from proc_start",
                },
                "input": {
                    "type": "string",
                    "description": "Text to send to the process",
                },
            },
            "required": ["proc_id", "input"],
        },
    ),
    Tool(
        name="linux_proc_read",
        description="Read output from a managed process with timeout.",
        inputSchema={
            "type": "object",
            "properties": {
                "proc_id": {
                    "type": "string",
                    "description": "Process ID",
                },
                "timeout_ms": {
                    "type": "integer",
                    "description": "Max wait time in ms (default 1000, max 10000)",
                    "default": 1000,
                },
            },
            "required": ["proc_id"],
        },
    ),
    Tool(
        name="linux_proc_stop",
        description="Stop a managed process and clean up.",
        inputSchema={
            "type": "object",
            "properties": {
                "proc_id": {
                    "type": "string",
                    "description": "Process ID to stop",
                },
                "signal": {
                    "type": "string",
                    "enum": ["TERM", "KILL", "INT", "HUP"],
                    "description": "Signal to send (default TERM)",
                    "default": "TERM",
                },
            },
            "required": ["proc_id"],
        },
    ),
    # L1 Phase 2 - FS Write Tools
    Tool(
        name="linux_fs_write",
        description="Write or append text to a file. Supports atomic writes and SHA256 precondition checks.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Text content to write"},
                "mode": {"type": "string", "enum": ["rewrite", "append"], "default": "rewrite"},
                "expected_sha256": {
                    "type": "string",
                    "description": "If set, verify file hash before write",
                },
            },
            "required": ["path", "content"],
        },
    ),
    Tool(
        name="linux_fs_mkdir",
        description="Create a directory (and parent directories if needed).",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to create"},
                "exist_ok": {"type": "boolean", "default": True},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="linux_fs_move",
        description="Move or rename a file or directory.",
        inputSchema={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source path"},
                "dest": {"type": "string", "description": "Destination path"},
            },
            "required": ["source", "dest"],
        },
    ),
    Tool(
        name="linux_fs_delete",
        description="Delete a file or directory.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to delete"},
                "recursive": {
                    "type": "boolean",
                    "default": False,
                    "description": "Required for directories",
                },
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="linux_fs_edit",
        description="Surgical text replacement in a file. Finds and replaces exact text matches.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File to edit"},
                "old_text": {"type": "string", "description": "Text to find"},
                "new_text": {"type": "string", "description": "Replacement text"},
                "expected_replacements": {
                    "type": "integer",
                    "default": 1,
                    "description": "Expected match count",
                },
            },
            "required": ["path", "old_text", "new_text"],
        },
    ),
]

# Code execution mode tool (Phase 2 - Anthropic Code Mode pattern)
EXECUTE_CODE_TOOL = Tool(
    name="execute_code",
    description="""Execute Python code with access to ALL LLMC tools via stubs.

WORKFLOW:
1. Use list_dir('.llmc/stubs/') to see available tools
2. Use read_file to check any stub's function signature
3. Write Python that imports and calls what you need

EXAMPLE:
```python
from stubs import rag_search
results = rag_search(query="router")
print(results['data'][0]['path'])
```

Tools: rag_search, rag_query, linux_fs_*, linux_proc_*, run_cmd, and more.
Only stdout is returned - filter data locally to save tokens.""",
    inputSchema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Use 'from stubs import tool_name' to access tools.",
            },
        },
        "required": ["code"],
    },
)


class LlmcMcpServer:
    """LLMC MCP Server implementation."""

    def __init__(self, config: McpConfig):
        self.config = config
        self.server = Server("llmc-mcp", instructions=BOOTSTRAP_PROMPT)

        # Initialize observability (M4)
        self.obs = ObservabilityContext(config.observability)

        # Check for code execution mode (Phase 2)
        if config.code_execution.enabled:
            self._init_code_execution_mode()
        else:
            self._init_classic_mode()

        self._register_dynamic_executables()
        self._register_handlers()
        logger.info(
            f"LLMC MCP Server initialized ({config.config_version}, mode={'code_exec' if config.code_execution.enabled else 'classic'})"
        )

    def _init_classic_mode(self):
        """Initialize classic mode with all 23 tools registered."""
        self.tools = list(TOOLS)
        self.tool_handlers = {
            "rag_search": self._handle_rag_search,
            "read_file": self._handle_read_file,
            "list_dir": self._handle_list_dir,
            "stat": self._handle_stat,
            "run_cmd": self._handle_run_cmd,
            "get_metrics": self._handle_get_metrics,
            "te_run": self._handle_te_run,
            "repo_read": self._handle_repo_read,
            "rag_query": self._handle_rag_query,
            "rag_search_enriched": self._handle_rag_search_enriched,
            "rag_where_used": self._handle_rag_where_used,
            "rag_lineage": self._handle_rag_lineage,
            "inspect": self._handle_inspect,
            "rag_stats": self._handle_rag_stats,
            # L2 LinuxOps
            "linux_proc_list": self._handle_proc_list,
            "linux_proc_kill": self._handle_proc_kill,
            "linux_sys_snapshot": self._handle_sys_snapshot,
            # L3 LinuxOps - REPLs
            "linux_proc_start": self._handle_proc_start,
            "linux_proc_send": self._handle_proc_send,
            "linux_proc_read": self._handle_proc_read,
            "linux_proc_stop": self._handle_proc_stop,
            # L1 Phase 2 - FS Writes
            "linux_fs_write": self._handle_fs_write,
            "linux_fs_mkdir": self._handle_fs_mkdir,
            "linux_fs_move": self._handle_fs_move,
            "linux_fs_delete": self._handle_fs_delete,
            "linux_fs_edit": self._handle_fs_edit,
        }
        logger.info("Classic mode: 23 tools registered")

    def _init_code_execution_mode(self):
        """
        Initialize code execution mode (Phase 2 - Anthropic Code Mode pattern).

        Only bootstrap tools are registered as MCP tools.
        All other tools become importable stubs in .llmc/stubs/.
        Claude navigates the stubs directory, reads definitions on-demand,
        writes Python code that imports and calls them.

        98% token reduction vs classic mode.
        """
        from llmc_mcp.tools.code_exec import generate_stubs

        # Get LLMC root
        llmc_root = (
            Path(self.config.tools.allowed_roots[0])
            if self.config.tools.allowed_roots
            else Path(".")
        )

        # Generate stubs for all tools
        stubs_dir = Path(self.config.code_execution.stubs_dir)
        logger.info(f"Code execution mode: generating stubs in {llmc_root / stubs_dir}")
        generated = generate_stubs(TOOLS, stubs_dir, llmc_root)
        logger.info(f"Generated {len(generated)} stub files")

        # Register only bootstrap tools + execute_code
        bootstrap = set(self.config.code_execution.bootstrap_tools)
        self.tools = [t for t in TOOLS if t.name in bootstrap]
        self.tools.append(EXECUTE_CODE_TOOL)

        # Minimal handler set for bootstrap tools
        self.tool_handlers = {
            "list_dir": self._handle_list_dir,
            "read_file": self._handle_read_file,
            "execute_code": self._handle_execute_code,
        }

        logger.info(f"Code execution mode: {len(self.tools)} bootstrap tools registered")

    async def _handle_execute_code(self, args: dict) -> list[TextContent]:
        """
        Handle execute_code tool - run Python code with access to tool stubs.

        This is the core of code execution mode. Claude writes Python code
        that imports from stubs and processes data locally. Only stdout
        is returned to the conversation context.
        """
        from llmc_mcp.tools.code_exec import execute_code

        code = args.get("code", "")
        if not code:
            return [TextContent(type="text", text='{"error": "code is required"}')]

        llmc_root = (
            Path(self.config.tools.allowed_roots[0])
            if self.config.tools.allowed_roots
            else Path(".")
        )
        stubs_dir = llmc_root / self.config.code_execution.stubs_dir

        # Create tool caller that routes back to our handlers
        def tool_caller(name: str, tool_args: dict) -> dict:
            """Synchronous tool caller for use within executed code."""
            handler = self.tool_handlers.get(name)
            if not handler:
                # Try classic handlers for stub calls
                classic_handlers = {
                    "rag_search": self._handle_rag_search,
                    "rag_search_enriched": self._handle_rag_search_enriched,
                    "read_file": self._handle_read_file,
                    "list_dir": self._handle_list_dir,
                    "stat": self._handle_stat,
                    "run_cmd": self._handle_run_cmd,
                    "te_run": self._handle_te_run,
                    "repo_read": self._handle_repo_read,
                    "rag_query": self._handle_rag_query,
                    "linux_proc_list": self._handle_proc_list,
                    "linux_proc_kill": self._handle_proc_kill,
                    "linux_sys_snapshot": self._handle_sys_snapshot,
                    "linux_proc_start": self._handle_proc_start,
                    "linux_proc_send": self._handle_proc_send,
                    "linux_proc_read": self._handle_proc_read,
                    "linux_proc_stop": self._handle_proc_stop,
                    "linux_fs_write": self._handle_fs_write,
                    "linux_fs_mkdir": self._handle_fs_mkdir,
                    "linux_fs_move": self._handle_fs_move,
                    "linux_fs_delete": self._handle_fs_delete,
                    "linux_fs_edit": self._handle_fs_edit,
                }
                handler = classic_handlers.get(name)

            if not handler:
                return {"error": f"Unknown tool: {name}"}

            # Run async handler synchronously (from thread pool to avoid nested loop issues)
            import concurrent.futures

            def _run_async():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    sig = inspect.signature(handler)
                    if "args" in sig.parameters:
                        return loop.run_until_complete(handler(tool_args))
                    else:
                        return loop.run_until_complete(handler())
                finally:
                    loop.close()

            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_run_async)
                    result = future.result(timeout=30)
                if result and result[0].text:
                    return json.loads(result[0].text)
                return {"error": "Empty result"}
            except Exception as e:
                return {"error": str(e)}

        result = execute_code(
            code=code,
            tool_caller=tool_caller,
            timeout=self.config.code_execution.timeout,
            max_output_bytes=self.config.code_execution.max_output_bytes,
            stubs_dir=stubs_dir,
        )

        response = {
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        if result.error:
            response["error"] = result.error
        if result.return_value is not None:
            response["return_value"] = result.return_value

        return [TextContent(type="text", text=json.dumps(response, indent=2))]

    def _register_dynamic_executables(self):
        """Register custom executables defined in config."""
        if not self.config.tools.executables:
            return

        for name, path in self.config.tools.executables.items():
            logger.info(f"Registering dynamic executable tool: {name} -> {path}")

            # Create Tool definition
            tool = Tool(
                name=name,
                description=f"Execute {path}",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Arguments to pass to the executable",
                        }
                    },
                    "required": [],
                },
            )
            self.tools.append(tool)

            # Register handler
            self.tool_handlers[name] = self._create_executable_handler(path)

    def _create_executable_handler(self, cmd_path: str) -> Callable:
        """Create a handler closure for a specific executable."""

        async def handler(args: dict) -> list[TextContent]:
            cmd_args = args.get("args", [])
            return await self._handle_run_executable(cmd_path, cmd_args)

        return handler

    async def _handle_run_executable(self, cmd_path: str, args: list[str]) -> list[TextContent]:
        """Execute a configured executable."""
        cwd = (
            Path(self.config.tools.allowed_roots[0])
            if self.config.tools.allowed_roots
            else Path(".")
        )

        # Construct command
        quoted_args = [shlex.quote(str(a)) for a in args]
        full_cmd = f"{shlex.quote(cmd_path)} {' '.join(quoted_args)}"

        try:
            result = subprocess.run(
                full_cmd,
                check=False,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.config.tools.exec_timeout,
            )

            response = {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
            }
            return [TextContent(type="text", text=json.dumps(response, indent=2))]

        except subprocess.TimeoutExpired:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": False,
                            "error": f"Command timed out after {self.config.tools.exec_timeout}s",
                            "exit_code": -1,
                        },
                        indent=2,
                    ),
                )
            ]
        except Exception as e:
            logger.exception(f"Error running {cmd_path}")
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"success": False, "error": str(e), "exit_code": -1}, indent=2),
                )
            ]

    def _register_handlers(self):
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """Return available tools."""
            logger.debug("list_tools called")
            return self.tools

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
                    assert handler is not None  # Mypy: handler can be None
                    # Handle args being optional for some handlers
                    from collections.abc import Callable  # Added for Callable type hint
                    import inspect

                    sig = inspect.signature(cast(Callable[..., Any], handler))
                    if "args" in sig.parameters:
                        result = await handler(arguments)
                    else:
                        result = await handler()
                else:
                    success = False
                    error_msg = f"Unknown tool: {name}"
                    result = [
                        TextContent(
                            type="text",
                            text=f'{{"error": "{error_msg}"}}',
                        )
                    ]

                # Check for error in result (soft failure)
                if result and result[0].text:
                    if '"error"' in result[0].text:  # Still check for the string "error"
                        success = False
                        try:
                            data = json.loads(result[0].text)
                            if "error" in data:
                                error_msg = data["error"]
                        except json.JSONDecodeError:
                            # If not valid JSON, just use the whole text as error message
                            error_msg = result[0].text
            except Exception as e:
                success = False
                error_msg = str(e)
                logger.exception(
                    f"Tool {name} failed: {e}", extra={"correlation_id": cid, "tool": name}
                )
                result = [
                    TextContent(
                        type="text",
                        text=f'{{"error": "{str(e)}"}}',
                    )
                ]

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
                    "error": error_msg,
                },
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

        # Use self.tools which includes dynamic ones
        data = [
            {"name": t.name, "description": t.description, "inputSchema": t.inputSchema}
            for t in self.tools
        ]
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    async def _handle_get_metrics(self) -> list[TextContent]:
        """Get server metrics handler."""
        import json

        if not self.obs.enabled:
            return [
                TextContent(
                    type="text",
                    text='{"error": "Observability disabled in config (mcp.observability.enabled = false)"}',
                )
            ]

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
        llmc_root = (
            Path(self.config.tools.allowed_roots[0])
            if self.config.tools.allowed_roots
            else Path(".")
        )

        # Direct call - no subprocess overhead
        result = rag_search(
            query=query,
            repo_root=llmc_root,
            limit=limit,
            scope=scope,
        )

        if result.error:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": result.error}),
                )
            ]

        # Return normalized structure (data + meta)
        return [TextContent(type="text", text=json.dumps(result.to_dict(), indent=2))]

    async def _handle_rag_search_enriched(self, args: dict) -> list[TextContent]:
        """RAG search with graph enrichment - advanced mode."""
        import json

        from llmc_mcp.tools.rag import rag_search_enriched

        query = args.get("query", "")
        limit = min(args.get("limit", 5), self.config.rag.top_k * 2)
        enrich_mode = args.get("enrich_mode", "auto")
        graph_depth = min(args.get("graph_depth", 1), 3)  # Cap at 3
        include_features = args.get("include_features", False)

        if not query:
            return [TextContent(type="text", text='{"error": "query is required"}')]

        # Find LLMC root from config
        llmc_root = (
            Path(self.config.tools.allowed_roots[0])
            if self.config.tools.allowed_roots
            else Path(".")
        )

        # Direct call with enrichment
        result = rag_search_enriched(
            query=query,
            repo_root=llmc_root,
            limit=limit,
            enrich_mode=enrich_mode,
            graph_depth=graph_depth,
            include_features=include_features,
        )

        if result.error:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": result.error}),
                )
            ]

        # Return normalized structure (data + meta)
        return [TextContent(type="text", text=json.dumps(result.to_dict(), indent=2))]

    async def _handle_rag_where_used(self, args: dict) -> list[TextContent]:
        import json

        from tools.rag_nav.tool_handlers import tool_rag_where_used

        symbol = args.get("symbol", "")
        limit = args.get("limit", 50)

        if not symbol:
            return [TextContent(type="text", text='{"error": "symbol is required"}')]

        llmc_root = (
            Path(self.config.tools.allowed_roots[0])
            if self.config.tools.allowed_roots
            else Path(".")
        )

        try:
            result = tool_rag_where_used(llmc_root, symbol, limit=limit)
            return [TextContent(type="text", text=json.dumps(result.to_dict(), indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def _handle_rag_lineage(self, args: dict) -> list[TextContent]:
        import json

        from tools.rag_nav.tool_handlers import tool_rag_lineage

        symbol = args.get("symbol", "")
        direction = args.get("direction", "downstream")
        limit = args.get("limit", 50)

        if not symbol:
            return [TextContent(type="text", text='{"error": "symbol is required"}')]

        llmc_root = (
            Path(self.config.tools.allowed_roots[0])
            if self.config.tools.allowed_roots
            else Path(".")
        )

        try:
            result = tool_rag_lineage(llmc_root, symbol, direction, max_results=limit)
            return [TextContent(type="text", text=json.dumps(result.to_dict(), indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def _handle_inspect(self, args: dict) -> list[TextContent]:
        import json

        from tools.rag.inspector import inspect_entity

        path = args.get("path")
        symbol = args.get("symbol")
        include_full_source = args.get("include_full_source", False)
        max_neighbors = args.get("max_neighbors", 3)

        if not path and not symbol:
            return [TextContent(type="text", text='{"error": "path or symbol is required"}')]

        llmc_root = (
            Path(self.config.tools.allowed_roots[0])
            if self.config.tools.allowed_roots
            else Path(".")
        )

        try:
            # inspect_entity returns InspectionResult dataclass
            result = inspect_entity(
                llmc_root,
                symbol=symbol,
                path=path,
                include_full_source=include_full_source,
                max_neighbors=max_neighbors,
            )
            return [TextContent(type="text", text=json.dumps(result.to_dict(), indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def _handle_rag_stats(self, args: dict) -> list[TextContent]:
        import json

        from tools.rag_nav.tool_handlers import tool_rag_stats

        llmc_root = (
            Path(self.config.tools.allowed_roots[0])
            if self.config.tools.allowed_roots
            else Path(".")
        )

        try:
            result = tool_rag_stats(llmc_root)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

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
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"data": result.data, "meta": result.meta}),
                )
            ]
        else:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": result.error, "meta": result.meta}),
                )
            ]

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
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"data": result.data, "meta": result.meta}),
                )
            ]
        else:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": result.error, "meta": result.meta}),
                )
            ]

    async def _handle_stat(self, args: dict) -> list[TextContent]:
        """Stat path handler."""
        import json

        from llmc_mcp.tools.fs import stat_path

        path = args.get("path", "")

        if not path:
            return [TextContent(type="text", text='{"error": "path is required"}')]

        result = stat_path(path, self.config.tools.allowed_roots)

        if result.success:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"data": result.data, "meta": result.meta}),
                )
            ]
        else:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": result.error, "meta": result.meta}),
                )
            ]

    async def _handle_run_cmd(self, args: dict) -> list[TextContent]:
        """Execute command handler with smart RAG hints for search patterns."""
        import json
        import re

        from llmc_mcp.tools.cmd import run_cmd
        from llmc_mcp.tools.rag import rag_search_enriched

        command = args.get("command", "")
        timeout = args.get("timeout", self.config.tools.exec_timeout)

        if not command:
            return [TextContent(type="text", text='{"error": "command is required"}')]

        if not self.config.tools.enable_run_cmd:
            return [
                TextContent(
                    type="text",
                    text='{"error": "run_cmd is disabled in config (mcp.tools.enable_run_cmd = false)"}',
                )
            ]

        # Get working directory (first allowed root)
        cwd = (
            Path(self.config.tools.allowed_roots[0])
            if self.config.tools.allowed_roots
            else Path(".")
        )

        # Smart grep interceptor: detect search patterns and show RAG preview
        grep_pattern = None

        # Detect grep -r / grep -R
        if "grep -r" in command.lower() or "grep -R" in command.lower():
            match = re.search(r'grep\s+-[rR]\w*\s+["\']?([^"\']+)["\']?', command)
            if match:
                grep_pattern = match.group(1)
        # Detect ripgrep (rg)
        elif command.strip().startswith("rg "):
            match = re.search(r'rg\s+["\']?([^"\']+)["\']?', command)
            if match:
                grep_pattern = match.group(1)

        # If we detected a search pattern worth trying RAG on
        if grep_pattern and len(grep_pattern) > 2 and not grep_pattern.startswith("-"):
            try:
                # Try RAG search first
                rag_result = rag_search_enriched(
                    query=grep_pattern,
                    repo_root=cwd,
                    limit=5,
                    enrich_mode="auto",
                    include_features=False,
                )

                if not rag_result.error and rag_result.data:
                    # Format RAG preview
                    preview = "🎯 Smart Search Results (AI-powered semantic search):\n\n"
                    for i, item in enumerate(rag_result.data[:5], 1):
                        lines = item.get("lines", [0, 0])
                        preview += f"{i}. {item['path']}:{lines[0]}-{lines[1]}\n"
                        preview += f"   Symbol: {item['symbol']} ({item['kind']})\n"
                        preview += f"   Relevance: {item['score']:.3f}\n"
                        if item.get("summary"):
                            summary = item["summary"][:120]
                            preview += (
                                f"   {summary}{'...' if len(item['summary']) > 120 else ''}\n"
                            )
                        preview += "\n"

                    preview += "💡 These are semantic search results with AI understanding.\n"
                    preview += "   They find MEANING, not just text matches.\n"
                    preview += f"   Original command: {command}\n"
                    preview += "   Run the original command if you need exact string matching.\n"

                    # Return RAG results instead of grep
                    return [
                        TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "success": True,
                                    "smart_search": True,
                                    "stdout": preview,
                                    "rag_results": rag_result.data,
                                    "original_command": command,
                                    "hint": "Smart search intercepted grep. These semantic results are often better. Use grep directly if you need exact text matching.",
                                },
                                indent=2,
                            ),
                        )
                    ]

            except Exception as e:
                # If RAG fails, fall through to normal grep
                logger.debug(f"Smart grep RAG fallback failed: {e}")

        # Normal command execution
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

    async def _handle_te_run(self, args: dict) -> list[TextContent]:
        """Execute command through TE wrapper."""
        import json

        from llmc_mcp.context import McpSessionContext
        from llmc_mcp.tools.te import te_run

        cmd_args = args.get("args", [])
        cwd_str = args.get("cwd")
        timeout = args.get("timeout", self.config.tools.exec_timeout)

        if not cmd_args or not isinstance(cmd_args, list):
            return [TextContent(type="text", text='{"error": "args list is required"}')]

        # Resolve CWD: must be allowed
        allowed_roots = [Path(p).resolve() for p in self.config.tools.allowed_roots]
        cwd = allowed_roots[0]  # Default to first root

        if cwd_str:
            requested_cwd = Path(cwd_str).resolve()
            # Verify within allowed roots
            is_allowed = False
            for root in allowed_roots:
                try:
                    requested_cwd.relative_to(root)
                    is_allowed = True
                    break
                except ValueError:
                    continue

            if is_allowed:
                cwd = requested_cwd
            else:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": f"cwd '{cwd_str}' not allowed", "meta": {}}),
                    )
                ]

        # Build context from environment (in a real server, this would come from request headers)
        ctx = McpSessionContext.from_env()

        # Execute
        result = te_run(
            cmd_args,
            ctx=ctx,
            timeout=min(timeout, self.config.tools.exec_timeout),
            cwd=str(cwd),
        )

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _handle_repo_read(self, args: dict) -> list[TextContent]:
        """Handle repo_read tool."""
        import json

        from llmc_mcp.context import McpSessionContext
        from llmc_mcp.tools.te_repo import repo_read

        root = args.get("root")
        path = args.get("path")
        max_bytes = args.get("max_bytes")

        if not root or not path:
            return [TextContent(type="text", text='{"error": "root and path are required"}')]

        ctx = McpSessionContext.from_env()

        result = repo_read(root=root, path=path, max_bytes=max_bytes, ctx=ctx)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _handle_rag_query(self, args: dict) -> list[TextContent]:
        """Handle rag_query tool - direct RAG adapter (no te dependency)."""
        import json

        from llmc_mcp.tools.rag import rag_search

        query = args.get("query")
        limit = args.get("k", 5)
        # Note: index and filters args are ignored for now (not supported by direct adapter)
        # index = args.get("index")
        # filters = args.get("filters")

        if not query:
            return [TextContent(type="text", text='{"error": "query is required"}')]

        # Find LLMC root from config
        llmc_root = (
            Path(self.config.tools.allowed_roots[0])
            if self.config.tools.allowed_roots
            else Path(".")
        )

        # Direct call - no subprocess/te overhead
        result = rag_search(
            query=query,
            repo_root=llmc_root,
            limit=limit,
            scope="repo",
        )

        if result.error:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": result.error}),
                )
            ]

        # Return normalized structure (data + meta)
        return [TextContent(type="text", text=json.dumps(result.to_dict(), indent=2))]

    # L2 LinuxOps handlers
    async def _handle_proc_list(self, args: dict) -> list[TextContent]:
        """Handle linux_proc_list tool."""
        from llmc_mcp.tools.linux_ops.errors import LinuxOpsError
        from llmc_mcp.tools.linux_ops.proc import mcp_linux_proc_list

        max_results = args.get("max_results", 200)
        user = args.get("user")

        try:
            result = mcp_linux_proc_list(
                config=self.config.linux_ops,
                max_results=max_results,
                user=user,
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except LinuxOpsError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e), "code": e.code}))]

    async def _handle_proc_kill(self, args: dict) -> list[TextContent]:
        """Handle linux_proc_kill tool."""
        from llmc_mcp.tools.linux_ops.errors import LinuxOpsError
        from llmc_mcp.tools.linux_ops.proc import mcp_linux_proc_kill

        pid = args.get("pid")
        signal = args.get("signal", "TERM")

        if pid is None:
            return [TextContent(type="text", text='{"error": "pid is required"}')]

        try:
            result = mcp_linux_proc_kill(
                config=self.config.linux_ops,
                pid=pid,
                signal=signal,
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except LinuxOpsError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e), "code": e.code}))]

    async def _handle_sys_snapshot(self, args: dict) -> list[TextContent]:
        """Handle linux_sys_snapshot tool."""
        from llmc_mcp.tools.linux_ops.errors import LinuxOpsError
        from llmc_mcp.tools.linux_ops.sysinfo import mcp_linux_sys_snapshot

        try:
            result = mcp_linux_sys_snapshot(config=self.config.linux_ops)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except LinuxOpsError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e), "code": e.code}))]

    # L3 LinuxOps - REPL handlers
    async def _handle_proc_start(self, args: dict) -> list[TextContent]:
        """Handle linux_proc_start tool."""
        from llmc_mcp.tools.linux_ops.errors import LinuxOpsError
        from llmc_mcp.tools.linux_ops.proc import mcp_linux_proc_start

        command = args.get("command")
        cwd = args.get("cwd")
        initial_timeout = args.get("initial_read_timeout_ms", 1000)

        if not command:
            return [TextContent(type="text", text='{"error": "command is required"}')]

        try:
            result = mcp_linux_proc_start(
                command=command,
                cwd=cwd,
                initial_read_timeout_ms=initial_timeout,
                config=self.config.linux_ops,
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except LinuxOpsError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e), "code": e.code}))]

    async def _handle_proc_send(self, args: dict) -> list[TextContent]:
        """Handle linux_proc_send tool."""
        from llmc_mcp.tools.linux_ops.errors import LinuxOpsError
        from llmc_mcp.tools.linux_ops.proc import mcp_linux_proc_send

        proc_id = args.get("proc_id")
        input_text = args.get("input")

        if not proc_id or input_text is None:
            return [TextContent(type="text", text='{"error": "proc_id and input are required"}')]

        try:
            result = mcp_linux_proc_send(
                proc_id=proc_id,
                input=input_text,
                config=self.config.linux_ops,
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except LinuxOpsError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e), "code": e.code}))]

    async def _handle_proc_read(self, args: dict) -> list[TextContent]:
        """Handle linux_proc_read tool."""
        from llmc_mcp.tools.linux_ops.errors import LinuxOpsError
        from llmc_mcp.tools.linux_ops.proc import mcp_linux_proc_read

        proc_id = args.get("proc_id")
        timeout_ms = args.get("timeout_ms", 1000)

        if not proc_id:
            return [TextContent(type="text", text='{"error": "proc_id is required"}')]

        try:
            result = mcp_linux_proc_read(
                proc_id=proc_id,
                timeout_ms=timeout_ms,
                config=self.config.linux_ops,
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except LinuxOpsError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e), "code": e.code}))]

    async def _handle_proc_stop(self, args: dict) -> list[TextContent]:
        """Handle linux_proc_stop tool."""
        from llmc_mcp.tools.linux_ops.errors import LinuxOpsError
        from llmc_mcp.tools.linux_ops.proc import mcp_linux_proc_stop

        proc_id = args.get("proc_id")
        signal = args.get("signal", "TERM")

        if not proc_id:
            return [TextContent(type="text", text='{"error": "proc_id is required"}')]

        try:
            result = mcp_linux_proc_stop(
                proc_id=proc_id,
                signal=signal,
                config=self.config.linux_ops,
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except LinuxOpsError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e), "code": e.code}))]

    # L1 Phase 2 - FS Write handlers
    async def _handle_fs_write(self, args: dict) -> list[TextContent]:
        """Handle linux_fs_write tool."""
        from llmc_mcp.tools.fs import write_file

        path = args.get("path", "")
        content = args.get("content", "")
        mode = args.get("mode", "rewrite")
        expected_sha256 = args.get("expected_sha256")
        if not path or content is None:
            return [TextContent(type="text", text='{"error": "path and content required"}')]
        result = write_file(path, self.config.tools.allowed_roots, content, mode, expected_sha256)
        if result.success:
            return [
                TextContent(
                    type="text", text=json.dumps({"data": result.data, "meta": result.meta})
                )
            ]
        return [
            TextContent(type="text", text=json.dumps({"error": result.error, "meta": result.meta}))
        ]

    async def _handle_fs_mkdir(self, args: dict) -> list[TextContent]:
        """Handle linux_fs_mkdir tool."""
        from llmc_mcp.tools.fs import create_directory

        path = args.get("path", "")
        exist_ok = args.get("exist_ok", True)
        if not path:
            return [TextContent(type="text", text='{"error": "path required"}')]
        result = create_directory(path, self.config.tools.allowed_roots, exist_ok)
        if result.success:
            return [
                TextContent(
                    type="text", text=json.dumps({"data": result.data, "meta": result.meta})
                )
            ]
        return [
            TextContent(type="text", text=json.dumps({"error": result.error, "meta": result.meta}))
        ]

    async def _handle_fs_move(self, args: dict) -> list[TextContent]:
        """Handle linux_fs_move tool."""
        from llmc_mcp.tools.fs import move_file

        source = args.get("source", "")
        dest = args.get("dest", "")
        if not source or not dest:
            return [TextContent(type="text", text='{"error": "source and dest required"}')]
        result = move_file(source, dest, self.config.tools.allowed_roots)
        if result.success:
            return [
                TextContent(
                    type="text", text=json.dumps({"data": result.data, "meta": result.meta})
                )
            ]
        return [
            TextContent(type="text", text=json.dumps({"error": result.error, "meta": result.meta}))
        ]

    async def _handle_fs_delete(self, args: dict) -> list[TextContent]:
        """Handle linux_fs_delete tool."""
        from llmc_mcp.tools.fs import delete_file

        path = args.get("path", "")
        recursive = args.get("recursive", False)
        if not path:
            return [TextContent(type="text", text='{"error": "path required"}')]
        result = delete_file(path, self.config.tools.allowed_roots, recursive)
        if result.success:
            return [
                TextContent(
                    type="text", text=json.dumps({"data": result.data, "meta": result.meta})
                )
            ]
        return [
            TextContent(type="text", text=json.dumps({"error": result.error, "meta": result.meta}))
        ]

    async def _handle_fs_edit(self, args: dict) -> list[TextContent]:
        """Handle linux_fs_edit tool."""
        from llmc_mcp.tools.fs import edit_block

        path = args.get("path", "")
        old_text = args.get("old_text", "")
        new_text = args.get("new_text", "")
        expected = args.get("expected_replacements", 1)
        if not path or not old_text:
            return [TextContent(type="text", text='{"error": "path and old_text required"}')]
        result = edit_block(path, self.config.tools.allowed_roots, old_text, new_text, expected)
        if result.success:
            return [
                TextContent(
                    type="text", text=json.dumps({"data": result.data, "meta": result.meta})
                )
            ]
        return [
            TextContent(type="text", text=json.dumps({"error": result.error, "meta": result.meta}))
        ]

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
        "--config",
        "-c",
        help="Path to llmc.toml config file",
        default=None,
    )
    parser.add_argument(
        "--log-level",
        "-l",
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
    global logger  # noqa: PLW0603
    if config.observability.enabled:
        logger = setup_logging(config.observability, "llmc-mcp")
    else:
        log_level = getattr(logging, config.server.log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(log_level)
        logger.setLevel(log_level)

    # Log effective config (minus secrets)
    logger.info(f"Config loaded: enabled={config.enabled}, version={config.config_version}")
    logger.info(
        f"Tools: allowed_roots={config.tools.allowed_roots}, run_cmd={config.tools.enable_run_cmd}"
    )
    logger.info(f"RAG: scope={config.rag.default_scope}, top_k={config.rag.top_k}")
    logger.info(
        f"Observability: enabled={config.observability.enabled}, log_format={config.observability.log_format}"
    )

    if not config.enabled:
        logger.warning("MCP server disabled in config, exiting")
        sys.exit(0)

    # Create and run server
    server = LlmcMcpServer(config)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
