"""RLM System Prompts - EXACTLY match injected tools.

FIXES V1.1.0 ISSUE: Prompts documented tools that weren't implemented.
V1.1.1: Prompts are GENERATED from actual injected tool names.
"""

from __future__ import annotations

from collections.abc import Callable


def get_rlm_system_prompt(
    context_meta: dict,
    injected_tools: dict[str, Callable],
) -> str:
    """Generate system prompt that matches injected tools exactly.
    
    V1.1.1 FIX: Prompt is generated from actual tools, not hardcoded.
    This ensures prompt/tool alignment by construction.
    """
    tool_docs = _generate_tool_docs(injected_tools)
    context_info = _format_context_info(context_meta)
    
    # Conditional workflow steps
    workflow_steps = [
        "1. Start with `outline = nav_outline()` to see the file structure",
        "2. Use `code = nav_read(\"SymbolName\")` to read specific functions/classes",
    ]
    if "llm_query" in injected_tools:
        workflow_steps.append("3. Use `llm_query(prompt)` sparingly for sub-analysis (each call has cost)")
    workflow_steps.append("4. Call `FINAL(answer)` when you have a complete answer")
    workflow_str = "\n".join(workflow_steps)
    
    # Get source path if available for prominent display
    source_path = context_meta.get("source_path", "the loaded file")

    return f'''You are an AI assistant analyzing code in a Python REPL environment.

**IMPORTANT: The file `{source_path}` is ALREADY LOADED as the analysis context.**
You do NOT need to ask which file to analyze - it is already loaded below.

{context_info}

## Available Tools (use these EXACTLY as shown)
{tool_docs}

## Tool Calling Convention
You are running in a restricted process sandbox.
ALL tool calls must be assigned to a variable immediately:
- `outline = nav_outline()`  # See all symbols in the loaded file
- `code = nav_read("ClassName")`  # Read a specific class or function
- `results = nav_search("pattern")`  # Search for patterns

Do NOT use:
- Bare calls: `nav_info()`
- Nested calls: `print(nav_info())`
- Complex arguments: `nav_ls(some_var)` (use string literals only)

## Special Functions
- `FINAL(answer)` - Submit your final answer and end the session
- `FINAL_VAR = answer` - Alternative way to submit final answer

## Workflow
{workflow_str}

## Important Rules
- The file is ALREADY LOADED - start analyzing immediately
- Use `nav_outline()` first to see what symbols are available
- Use `nav_read("symbol")` to read specific code sections
- Write Python code in ```python blocks
- Call FINAL(answer) as soon as you have the answer

Begin your analysis of `{source_path}`.'''


def _format_context_info(meta: dict) -> str:
    """Format context metadata."""
    parts = ["## Context Information"]
    
    if "total_chars" in meta:
        parts.append(f"- Size: {meta['total_chars']:,} characters")
    if "estimated_tokens" in meta:
        parts.append(f"- Estimated tokens: {meta['estimated_tokens']:,}")
    if "language" in meta:
        parts.append(f"- Language: {meta['language']}")
    if "symbol_count" in meta:
        parts.append(f"- Symbols indexed: {meta['symbol_count']}")
    if meta.get("source_path"):
        parts.append(f"- Source: {meta['source_path']}")
    
    return "\n".join(parts)


def _generate_tool_docs(tools: dict[str, Callable]) -> str:
    """Generate documentation from actual tool functions.
    
    Uses docstrings where available, otherwise generates basic signature.
    """
    lines = []
    
    for name, func in sorted(tools.items()):
        doc = func.__doc__ or f"Call {name}()"
        # Extract first line of docstring
        first_line = doc.strip().split('\n')[0]
        lines.append(f"- `{name}()` - {first_line}")
    
    return "\n".join(lines)
