"""Tool tier system for llmc_agent.

Progressive disclosure of capabilities:
- Tier 0 (Crawl): RAG search only - find things
- Tier 1 (Walk): Read operations - see things  
- Tier 2 (Run): Write operations - change things

The agent starts at Tier 0 and unlocks higher tiers based on detected intent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable


class ToolTier(IntEnum):
    """Tool capability tiers."""
    
    CRAWL = 0  # Search/discovery only
    WALK = 1   # Read operations
    RUN = 2    # Write operations


@dataclass
class Tool:
    """A tool available to the agent."""
    
    name: str
    description: str
    tier: ToolTier
    function: Callable[..., Any]
    parameters: dict[str, Any]  # JSON Schema
    requires_confirmation: bool = False
    
    def to_ollama_format(self) -> dict[str, Any]:
        """Convert to Ollama tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


# ============================================================================
# Tool Definitions
# ============================================================================

def _make_rag_search_tool() -> Tool:
    """RAG search tool (Tier 0)."""
    from llmc_agent.backends.llmc import LLMCBackend
    
    backend = LLMCBackend()
    
    async def rag_search(query: str, limit: int = 5) -> dict[str, Any]:
        """Search the codebase for relevant code."""
        results = await backend.search(query, limit=limit)
        return {
            "results": [
                {
                    "path": r.path,
                    "lines": f"{r.start_line}-{r.end_line}",
                    "snippet": r.snippet[:300],
                    "summary": r.summary,
                }
                for r in results
            ]
        }
    
    return Tool(
        name="search_code",
        description="Search the codebase for relevant code snippets. Use this to find functions, classes, or concepts.",
        tier=ToolTier.CRAWL,
        function=rag_search,
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default 5)",
                    "default": 5,
                }
            },
            "required": ["query"]
        }
    )


def _make_read_file_tool(allowed_roots: list[str]) -> Tool:
    """Read file tool (Tier 1)."""
    from llmc_mcp.tools.fs import read_file as fs_read_file
    
    def read_file(path: str, max_lines: int = 200) -> dict[str, Any]:
        """Read contents of a file."""
        result = fs_read_file(path, allowed_roots, max_bytes=max_lines * 100)
        if result.success:
            content = result.data
            lines = content.split("\n")
            if len(lines) > max_lines:
                content = "\n".join(lines[:max_lines]) + f"\n\n[...truncated, {len(lines) - max_lines} more lines...]"
            return {"content": content, "path": path, "truncated": len(lines) > max_lines}
        else:
            return {"error": result.error, "path": path}
    
    return Tool(
        name="read_file",
        description="Read the contents of a file. Use after search_code to see full context.",
        tier=ToolTier.WALK,
        function=read_file,
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read"
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum lines to return (default 200)",
                    "default": 200,
                }
            },
            "required": ["path"]
        }
    )


def _make_list_dir_tool(allowed_roots: list[str]) -> Tool:
    """List directory tool (Tier 1)."""
    from llmc_mcp.tools.fs import list_dir as fs_list_dir
    
    def list_directory(path: str, include_hidden: bool = False) -> dict[str, Any]:
        """List contents of a directory."""
        result = fs_list_dir(path, allowed_roots, include_hidden=include_hidden)
        if result.success:
            return {"entries": result.data, "path": path}
        else:
            return {"error": result.error, "path": path}
    
    return Tool(
        name="list_dir",
        description="List files and subdirectories in a directory.",
        tier=ToolTier.WALK,
        function=list_directory,
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list"
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Include hidden files (default false)",
                    "default": False,
                }
            },
            "required": ["path"]
        }
    )


def _make_edit_block_tool(allowed_roots: list[str]) -> Tool:
    """Edit block tool (Tier 2)."""
    from llmc_mcp.tools.fs import edit_block as fs_edit_block
    
    def edit_block(path: str, old_text: str, new_text: str) -> dict[str, Any]:
        """Replace text in a file."""
        result = fs_edit_block(path, allowed_roots, old_text, new_text)
        if result.success:
            return {
                "success": True,
                "path": path,
                "replacements": result.data.get("replacements", 1),
            }
        else:
            return {"success": False, "error": result.error, "path": path}
    
    return Tool(
        name="edit_block",
        description="Replace a block of text in a file. The old_text must match exactly.",
        tier=ToolTier.RUN,
        function=edit_block,
        requires_confirmation=True,
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file to edit"
                },
                "old_text": {
                    "type": "string",
                    "description": "Exact text to find and replace"
                },
                "new_text": {
                    "type": "string",
                    "description": "Replacement text"
                }
            },
            "required": ["path", "old_text", "new_text"]
        }
    )


def _make_write_file_tool(allowed_roots: list[str]) -> Tool:
    """Write file tool (Tier 2)."""
    from llmc_mcp.tools.fs import write_file as fs_write_file
    
    def write_file(path: str, content: str, mode: str = "rewrite") -> dict[str, Any]:
        """Write content to a file."""
        result = fs_write_file(path, allowed_roots, content, mode=mode)
        if result.success:
            return {"success": True, "path": path, "bytes_written": len(content)}
        else:
            return {"success": False, "error": result.error, "path": path}
    
    return Tool(
        name="write_file",
        description="Write or create a file. Use mode='append' to add to existing file.",
        tier=ToolTier.RUN,
        function=write_file,
        requires_confirmation=True,
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file to write"
                },
                "content": {
                    "type": "string", 
                    "description": "Content to write"
                },
                "mode": {
                    "type": "string",
                    "enum": ["rewrite", "append"],
                    "description": "Write mode (default: rewrite)",
                    "default": "rewrite"
                }
            },
            "required": ["path", "content"]
        }
    )


def _make_inspect_tool() -> Tool:
    """Inspect code tool (Tier 1) - span-aware with enrichment."""
    from pathlib import Path
    
    def inspect_code(path: str, symbol: str | None = None, line: int | None = None) -> dict[str, Any]:
        """Inspect a file or symbol with RAG enrichment.
        
        Returns focused snippets instead of whole files - much more context efficient!
        """
        try:
            from tools.rag.inspector import inspect_entity, PathSecurityError
            
            repo_root = Path.cwd()
            
            result = inspect_entity(
                repo_root,
                path=path if not symbol else None,
                symbol=symbol,
                line=line,
                include_full_source=False,  # Just snippets
                max_neighbors=3,
            )
            
            return {
                "path": result.path,
                "snippet": result.snippet,
                "span": result.primary_span,
                "summary": result.file_summary,
                "symbols": [
                    {"name": s.name, "line": s.line, "type": s.type, "summary": s.summary}
                    for s in (result.defined_symbols or [])[:5]
                ],
                "enrichment": result.enrichment if result.enrichment else None,
            }
        except PathSecurityError as e:
            return {"error": f"Security: {e}", "path": path}
        except Exception as e:
            return {"error": str(e), "path": path}
    
    return Tool(
        name="inspect_code",
        description="Inspect a file or symbol with RAG context. Returns focused snippets with enrichment - use this instead of read_file for code understanding.",
        tier=ToolTier.WALK,
        function=inspect_code,
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to inspect"
                },
                "symbol": {
                    "type": "string",
                    "description": "Optional symbol name to focus on (e.g., 'MyClass.my_method')"
                },
                "line": {
                    "type": "integer",
                    "description": "Optional line number to focus on"
                }
            },
            "required": ["path"]
        }
    )


# ============================================================================
# Tool Registry
# ============================================================================

class ToolRegistry:
    """Manages available tools and tier transitions."""
    
    def __init__(self, allowed_roots: list[str] | None = None):
        self.allowed_roots = allowed_roots or ["."]
        self.current_tier = ToolTier.CRAWL
        self._tools: dict[str, Tool] = {}
        self._build_tools()
    
    def _build_tools(self) -> None:
        """Initialize all tools."""
        # Tier 0: Crawl
        self._register(_make_rag_search_tool())
        
        # Tier 1: Walk
        self._register(_make_read_file_tool(self.allowed_roots))
        self._register(_make_list_dir_tool(self.allowed_roots))
        self._register(_make_inspect_tool())
        
        # Tier 2: Run
        self._register(_make_edit_block_tool(self.allowed_roots))
        self._register(_make_write_file_tool(self.allowed_roots))
    
    def _register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def get_tools_for_tier(self, tier: ToolTier | None = None) -> list[Tool]:
        """Get tools available at a tier (includes lower tiers)."""
        tier = tier if tier is not None else self.current_tier
        return [t for t in self._tools.values() if t.tier <= tier]
    
    def get_tool(self, name: str) -> Tool | None:
        """Get a specific tool by name."""
        return self._tools.get(name)
    
    def is_tool_available(self, name: str) -> bool:
        """Check if tool is available at current tier."""
        tool = self._tools.get(name)
        if not tool:
            return False
        return tool.tier <= self.current_tier
    
    def unlock_tier(self, tier: ToolTier) -> None:
        """Unlock a capability tier."""
        if tier > self.current_tier:
            self.current_tier = tier
    
    def to_ollama_tools(self) -> list[dict[str, Any]]:
        """Get Ollama-formatted tool definitions for current tier."""
        return [t.to_ollama_format() for t in self.get_tools_for_tier()]
    
    def tier_token_cost(self, tier: ToolTier | None = None) -> int:
        """Estimate token cost of tool definitions for a tier."""
        tools = self.get_tools_for_tier(tier)
        # Rough estimate: ~50 tokens per tool definition
        return len(tools) * 50


# ============================================================================
# Intent Detection (for auto-tier-unlock)
# ============================================================================

# Keywords that suggest the user wants to read files
WALK_SIGNALS = [
    "show me", "read", "view", "see", "look at", "contents of",
    "what's in", "open", "display", "print",
]

# Keywords that suggest the user wants to modify files
RUN_SIGNALS = [
    "edit", "change", "modify", "update", "fix", "add", "remove",
    "create", "write", "delete", "replace", "refactor",
]


def detect_intent_tier(prompt: str) -> ToolTier:
    """Detect intent tier from user prompt."""
    prompt_lower = prompt.lower()
    
    # Check for Run signals first (higher priority)
    for signal in RUN_SIGNALS:
        if signal in prompt_lower:
            return ToolTier.RUN
    
    # Check for Walk signals
    for signal in WALK_SIGNALS:
        if signal in prompt_lower:
            return ToolTier.WALK
    
    # Default to Crawl
    return ToolTier.CRAWL
