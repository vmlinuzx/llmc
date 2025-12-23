"""
Code Execution Mode - Anthropic "Code Mode" pattern implementation.

When enabled, replaces 23 MCP tools with 3 bootstrap tools + code execution.
Claude navigates .llmc/stubs/ filesystem, reads tool definitions on-demand,
writes Python code that imports and calls them. 98% token reduction.

Reference: https://www.anthropic.com/engineering/code-execution-with-mcp

SECURITY:
The `run_untrusted_python` tool in this module does NOT provide a sandbox.
It is a critical vulnerability to use this tool outside of a securely isolated
environment (e.g., a locked-down Docker container).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import textwrap
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
    readme_content = (
        textwrap.dedent("""
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
    """).strip()
        + "\n"
    )

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


def run_untrusted_python(
    code: str,
    tool_caller: callable,
    timeout: int = 30,
    max_output_bytes: int = 65536,
    stubs_dir: Path | None = None,
) -> CodeExecResult:
    """
    Execute untrusted Python code without a sandbox.
    WARNING: This tool does NOT provide a sandbox. The executed code can access
    the filesystem and network. It is CRITICAL that this tool is only used in
    a securely isolated environment (e.g., a Docker container with restricted
    permissions).
    The code can import from 'stubs' to access tool functions.
    Only stdout/stderr and explicit return values are captured.
    
    SECURITY: 
    - CRITICAL: No sandbox is provided.
    - Requires isolated environment (Docker, K8s, nsjail).
    - Code runs in a subprocess for process isolation, but this does NOT
      prevent filesystem or network access.
    - NOTE: tool_caller is NOT available in subprocess mode (stubs won't work).
      This is a security tradeoff - full stub support requires the orchestrator
      pattern where Claude iterates: execute code -> get result -> execute more.

    Args:
        code: Python code to execute
        tool_caller: Function to call MCP tools (currently unused in subprocess mode)
        timeout: Max execution time in seconds
        max_output_bytes: Max bytes to capture from stdout/stderr
        stubs_dir: Path to stubs directory (added to PYTHONPATH)

    Returns:
        CodeExecResult with stdout, stderr, return_value, and error
    """
    import tempfile
    
    # SECURITY: Only allow execution in isolated environments
    from llmc_mcp.isolation import require_isolation
    try:
        require_isolation("run_untrusted_python")
    except RuntimeError as e:
        return CodeExecResult(
            success=False,
            stdout="",
            stderr=str(e),
            error=str(e),
        )
    
    # SECURITY: Process-based isolation
    # Write code to a temp file and execute in subprocess.
    # This prevents malicious code from accessing the MCP server's memory,
    # credentials, or state. The old exec() approach was vulnerable to
    # bypasses like __import__('os').
    
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False
        ) as f:
            f.write(code)
            temp_path = f.name
        
        # Build environment - inherit current env but can add stubs path
        env = dict(__import__('os').environ)
        if stubs_dir and stubs_dir.exists():
            current_pythonpath = env.get('PYTHONPATH', '')
            stubs_parent = str(stubs_dir.parent)
            if current_pythonpath:
                env['PYTHONPATH'] = f"{stubs_parent}:{current_pythonpath}"
            else:
                env['PYTHONPATH'] = stubs_parent
        
        # Execute in subprocess with timeout
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            timeout=timeout,
            env=env,
            cwd=str(stubs_dir.parent) if stubs_dir else None,
        )
        
        stdout = result.stdout.decode('utf-8', errors='replace')[:max_output_bytes]
        stderr = result.stderr.decode('utf-8', errors='replace')[:max_output_bytes]
        
        if result.returncode == 0:
            return CodeExecResult(
                success=True,
                stdout=stdout,
                stderr=stderr,
                return_value=None,  # Can't get return value from subprocess
            )
        else:
            return CodeExecResult(
                success=False,
                stdout=stdout,
                stderr=stderr,
                error=f"Process exited with code {result.returncode}",
            )

    except subprocess.TimeoutExpired:
        return CodeExecResult(
            success=False,
            stdout="",
            stderr="",
            error=f"Code execution timed out after {timeout}s",
        )
    except Exception as e:
        return CodeExecResult(
            success=False,
            stdout="",
            stderr="",
            error=f"{type(e).__name__}: {e}",
        )
    finally:
        # Clean up temp file
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception:
            pass
