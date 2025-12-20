#!/usr/bin/env python3
"""
Native Tool Scripts Integration for MCP Server.

Provides handlers that delegate to the native tool scripts in scripts/ directory.
This allows the MCP server to expose OpenAI/Anthropic/MCP-compatible tools.
"""
import json
import subprocess
from pathlib import Path
from typing import Any


# Script paths relative to repo root
NATIVE_TOOL_SCRIPTS = {
    # OpenAI tools
    "file_search": "scripts/openaitools/file_search",
    
    # MCP tools
    "read_text_file": "scripts/mcptools/read_text_file",
    "write_file": "scripts/mcptools/write_file",
    "list_directory": "scripts/mcptools/list_directory",
    "edit_file": "scripts/mcptools/edit_file",
    "search_files": "scripts/mcptools/search_files",
    
    # Anthropic tools
    "bash": "scripts/anthropictools/bash",
    "text_editor": "scripts/anthropictools/text_editor",
}


def call_native_tool(
    tool_name: str, 
    args: dict[str, Any], 
    repo_root: Path,
    timeout: int = 30,
    allowed_roots: list[str] | None = None,
) -> dict[str, Any]:
    """
    Call a native tool script and return the parsed JSON result.
    
    Args:
        tool_name: Name of the tool (must be in NATIVE_TOOL_SCRIPTS)
        args: Arguments to pass to the tool as JSON
        repo_root: Repository root directory
        timeout: Execution timeout in seconds
        allowed_roots: Optional list of allowed root paths for security
        
    Returns:
        Parsed JSON response from the tool
    """
    if tool_name not in NATIVE_TOOL_SCRIPTS:
        return {"success": False, "error": f"Unknown native tool: {tool_name}"}
    
    script_path = repo_root / NATIVE_TOOL_SCRIPTS[tool_name]
    
    if not script_path.exists():
        return {"success": False, "error": f"Script not found: {script_path}"}
    
    # Build environment
    env = {}
    if allowed_roots:
        env["LLMC_ALLOWED_ROOTS"] = ":".join(allowed_roots)
    else:
        env["LLMC_ALLOWED_ROOTS"] = str(repo_root)
    
    try:
        result = subprocess.run(
            [str(script_path), json.dumps(args)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(repo_root),
            env={**subprocess.os.environ, **env},
        )
        
        # Parse JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": f"Invalid JSON from script: {result.stdout[:500]}",
                "stderr": result.stderr,
            }
            
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Tool timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_native_tool_definitions() -> list[dict[str, Any]]:
    """
    Return OpenAI-style tool definitions for all native tools.
    
    These can be used to register tools with an MCP server or sent to an LLM.
    """
    return [
        {
            "name": "file_search",
            "description": "Semantic search over codebase (RAG). Returns ranked results with optional LLMC enrichment (graph context, summaries).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language query"},
                    "limit": {"type": "integer", "description": "Max results (default: 10)", "default": 10},
                    "include_content": {"type": "boolean", "description": "Include code snippets", "default": False},
                    "include_graph": {"type": "boolean", "description": "Include callers/callees", "default": True},
                    "include_enrichment": {"type": "boolean", "description": "Include summaries/pitfalls", "default": True},
                },
                "required": ["query"],
            },
        },
        {
            "name": "read_text_file",
            "description": "Read file contents as UTF-8 text.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"},
                    "head": {"type": "integer", "description": "Read first N lines only"},
                    "tail": {"type": "integer", "description": "Read last N lines only"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "write_file",
            "description": "Create or overwrite a file.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "list_directory",
            "description": "List directory contents with [FILE]/[DIR] prefixes.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "edit_file",
            "description": "Make pattern-based edits to a file (str_replace style).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to edit"},
                    "edits": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "oldText": {"type": "string"},
                                "newText": {"type": "string"},
                            },
                        },
                        "description": "List of {oldText, newText} replacements",
                    },
                    "dryRun": {"type": "boolean", "description": "Preview changes without applying", "default": False},
                },
                "required": ["path", "edits"],
            },
        },
        {
            "name": "search_files",
            "description": "Recursively search for files matching a glob pattern.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Starting directory"},
                    "pattern": {"type": "string", "description": "Glob pattern (e.g., *.py)"},
                    "excludePatterns": {"type": "array", "items": {"type": "string"}, "description": "Patterns to exclude"},
                },
                "required": ["path", "pattern"],
            },
        },
        {
            "name": "bash",
            "description": "Execute a shell command.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
                    "cwd": {"type": "string", "description": "Working directory"},
                },
                "required": ["command"],
            },
        },
        {
            "name": "text_editor",
            "description": "View and edit text files (view, create, str_replace, insert commands).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "enum": ["view", "create", "str_replace", "insert"], "description": "Editor command"},
                    "path": {"type": "string", "description": "File path"},
                    "view_range": {"type": "array", "items": {"type": "integer"}, "description": "[start, end] lines for view"},
                    "content": {"type": "string", "description": "Content for create/insert"},
                    "old_str": {"type": "string", "description": "String to replace (str_replace)"},
                    "new_str": {"type": "string", "description": "Replacement string (str_replace)"},
                    "insert_line": {"type": "integer", "description": "Line number for insert"},
                },
                "required": ["command", "path"],
            },
        },
    ]


# Convenience functions for direct tool calls
def file_search(query: str, limit: int = 10, repo_root: Path = Path("."), **kwargs) -> dict:
    """Semantic search over codebase."""
    return call_native_tool("file_search", {"query": query, "limit": limit, **kwargs}, repo_root)


def read_text_file(path: str, repo_root: Path = Path("."), **kwargs) -> dict:
    """Read file contents."""
    return call_native_tool("read_text_file", {"path": path, **kwargs}, repo_root)


def write_file(path: str, content: str, repo_root: Path = Path(".")) -> dict:
    """Write file."""
    return call_native_tool("write_file", {"path": path, "content": content}, repo_root)


def list_directory(path: str, repo_root: Path = Path(".")) -> dict:
    """List directory."""
    return call_native_tool("list_directory", {"path": path}, repo_root)


def edit_file(path: str, edits: list[dict], repo_root: Path = Path("."), dry_run: bool = False) -> dict:
    """Edit file with str_replace."""
    return call_native_tool("edit_file", {"path": path, "edits": edits, "dryRun": dry_run}, repo_root)


def search_files(path: str, pattern: str, repo_root: Path = Path("."), exclude: list[str] | None = None) -> dict:
    """Search for files."""
    args = {"path": path, "pattern": pattern}
    if exclude:
        args["excludePatterns"] = exclude
    return call_native_tool("search_files", args, repo_root)


def bash(command: str, repo_root: Path = Path("."), timeout: int = 30) -> dict:
    """Execute shell command."""
    return call_native_tool("bash", {"command": command, "timeout": timeout}, repo_root)


def text_editor(command: str, path: str, repo_root: Path = Path("."), **kwargs) -> dict:
    """Text editor operations."""
    return call_native_tool("text_editor", {"command": command, "path": path, **kwargs}, repo_root)
