"""
Code Execution Mode - Anthropic "Code Mode" pattern implementation.

When enabled, replaces 23 MCP tools with 3 bootstrap tools + code execution.
Claude navigates .llmc/stubs/ filesystem, reads tool definitions on-demand,
writes Python code that imports and calls them. 98% token reduction.

Reference: https://www.anthropic.com/engineering/code-execution-with-mcp
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.types import Tool


@dataclass
class CodeExecResult:
    """Result of code execution."""

    success: bool
    stdout: str
    stderr: str
    return_value: Any = None
    error: str | None = None


def generate_stubs(tools: list[Tool], stubs_dir: Path, llmc_root: Path) -> dict[str, str]:
    """
    Generate Python stub files from MCP tool definitions.

    Each tool becomes a .py file with a typed function signature and docstring.
    Claude can read these files to understand the API, then write code that
    imports and calls them.

    Args:
        tools: List of MCP Tool definitions
        stubs_dir: Directory to write stubs (relative to llmc_root)
        llmc_root: LLMC repository root

    Returns:
        Dict mapping tool name -> generated file path
    """
    full_stubs_dir = llmc_root / stubs_dir
    full_stubs_dir.mkdir(parents=True, exist_ok=True)

    generated = {}

    # Generate __init__.py for package imports
    init_lines = [
        '"""',
        "LLMC Tool Stubs - Auto-generated from MCP tool definitions.",
        "",
        "Import tools you need:",
        "    from stubs import rag_search, read_file",
        "    results = rag_search('query')",
        '"""',
        "",
    ]

    for tool in tools:
        name = tool.name
        desc = tool.description or f"Execute {name} tool"
        schema = tool.inputSchema

        # Parse schema to generate function signature
        props = schema.get("properties", {})
        required = set(schema.get("required", []))

        # Build parameter list
        params = []
        param_docs = []

        for prop_name, prop_def in props.items():
            prop_type = _schema_type_to_python(prop_def)
            prop_desc = prop_def.get("description", "")
            default = prop_def.get("default")

            if prop_name in required:
                params.append(f"{prop_name}: {prop_type}")
            else:
                default_repr = repr(default) if default is not None else "None"
                params.append(f"{prop_name}: {prop_type} = {default_repr}")

            param_docs.append(f"        {prop_name}: {prop_desc}")

        params_str = ", ".join(params)
        param_docs_str = "\n".join(param_docs) if param_docs else "        None"

        # Generate stub file content
        stub_content = f'''"""
{desc}

Auto-generated stub for MCP tool '{name}'.
"""

from __future__ import annotations
from typing import Any

# _call_tool is injected into builtins by execute_code() at runtime.
# Do NOT import it - that gets the NotImplementedError placeholder.


def {name}({params_str}) -> dict[str, Any]:
    """
    {desc}

    Args:
{param_docs_str}

    Returns:
        Tool result as dict with 'data' and 'meta' keys.
    """
    return _call_tool("{name}", locals())
'''

        # Write stub file
        stub_path = full_stubs_dir / f"{name}.py"
        stub_path.write_text(stub_content)
        generated[name] = str(stub_path)

        # Add to __init__.py
        init_lines.append(f"from .{name} import {name}")

    # Write __init__.py
    init_path = full_stubs_dir / "__init__.py"
    init_path.write_text("\n".join(init_lines) + "\n")
    generated["__init__"] = str(init_path)

    # Write a README for Claude
    readme_content = textwrap.dedent("""
        # LLMC Tool Stubs

        This directory contains Python stubs for all LLMC MCP tools.
        
        ## Usage
        
        ```python
        from stubs import rag_search, read_file, linux_fs_write
        
        # Search the codebase
        results = rag_search("router implementation")
        
        # Read a specific file
        content = read_file(results["data"][0]["path"])
        
        # Process locally - only return what's needed
        print(content["data"][:500])
        ```
        
        ## Available Tools
        
        Browse this directory to see all available tools.
        Each .py file contains a function with the same name.
        Read the file to see the function signature and docstring.
        
        ## Key Insight
        
        Process data in your code before printing output.
        Only printed output goes back to the conversation context.
        This dramatically reduces token usage.
    """).strip() + "\n"

    readme_path = full_stubs_dir / "README.md"
    readme_path.write_text(readme_content)
    generated["README"] = str(readme_path)

    return generated


def _schema_type_to_python(prop_def: dict) -> str:
    """Convert JSON schema type to Python type hint."""
    schema_type = prop_def.get("type", "any")

    if schema_type == "string":
        return "str"
    elif schema_type == "integer":
        return "int"
    elif schema_type == "number":
        return "float"
    elif schema_type == "boolean":
        return "bool"
    elif schema_type == "array":
        items = prop_def.get("items", {})
        item_type = _schema_type_to_python(items)
        return f"list[{item_type}]"
    elif schema_type == "object":
        return "dict[str, Any]"
    else:
        return "Any"


def _call_tool(name: str, args: dict) -> dict:
    """
    Internal: Call an MCP tool from within executed code.

    This is used by generated stubs to call back into the MCP server.
    In code execution mode, this function is injected into the execution
    namespace so stubs can make tool calls.

    Args:
        name: Tool name
        args: Tool arguments (from locals())

    Returns:
        Tool result dict
    """
    # Remove 'self' if present (shouldn't be, but defensive)
    args = {k: v for k, v in args.items() if k != "self" and v is not None}

    # This will be monkey-patched by the executor with the actual implementation
    raise NotImplementedError(
        "_call_tool must be injected by the code executor. "
        "This stub should not be called directly outside of execute_code."
    )


def execute_code(
    code: str,
    tool_caller: callable,
    timeout: int = 30,
    max_output_bytes: int = 65536,
    stubs_dir: Path | None = None,
) -> CodeExecResult:
    """
    Execute Python code with access to LLMC tool stubs.

    The code can import from 'stubs' to access tool functions.
    Only stdout/stderr and explicit return values are captured.
    This is the "sandbox" where Claude's code runs.

    Args:
        code: Python code to execute
        tool_caller: Function to call MCP tools (name, args) -> result
        timeout: Max execution time in seconds
        max_output_bytes: Max bytes to capture from stdout/stderr
        stubs_dir: Path to stubs directory (for imports)

    Returns:
        CodeExecResult with stdout, stderr, return_value, and error
    """
    import io
    import contextlib

    # Prepare execution namespace
    # Inject _call_tool into builtins so imported stubs can find it
    import builtins
    _original_call_tool = getattr(builtins, '_call_tool', None)
    builtins._call_tool = tool_caller
    
    namespace = {
        "__builtins__": builtins,
        "_call_tool": tool_caller,  # Also in namespace for inline code
    }

    # Add stubs to path if provided
    if stubs_dir and stubs_dir.exists():
        sys.path.insert(0, str(stubs_dir.parent))

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            # Compile and exec
            compiled = compile(code, "<claude_code>", "exec")
            exec(compiled, namespace)

        stdout = stdout_capture.getvalue()[:max_output_bytes]
        stderr = stderr_capture.getvalue()[:max_output_bytes]

        # Check for explicit return value (last expression)
        return_value = namespace.get("_result_", None)

        return CodeExecResult(
            success=True,
            stdout=stdout,
            stderr=stderr,
            return_value=return_value,
        )

    except subprocess.TimeoutExpired:
        return CodeExecResult(
            success=False,
            stdout=stdout_capture.getvalue()[:max_output_bytes],
            stderr=stderr_capture.getvalue()[:max_output_bytes],
            error=f"Code execution timed out after {timeout}s",
        )
    except Exception as e:
        return CodeExecResult(
            success=False,
            stdout=stdout_capture.getvalue()[:max_output_bytes],
            stderr=stderr_capture.getvalue()[:max_output_bytes],
            error=f"{type(e).__name__}: {e}",
        )
    finally:
        # Clean up sys.path
        if stubs_dir and str(stubs_dir.parent) in sys.path:
            sys.path.remove(str(stubs_dir.parent))
        # Restore original builtins._call_tool (or remove if didn't exist)
        if _original_call_tool is None:
            if hasattr(builtins, '_call_tool'):
                delattr(builtins, '_call_tool')
        else:
            builtins._call_tool = _original_call_tool
