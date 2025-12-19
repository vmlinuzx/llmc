# SDD: Thin CLI Wrappers with Graph Enrichment (Roadmap 2.2)

**Date:** 2025-12-19  
**Author:** Dave + Antigravity  
**Status:** Ready for Implementation  
**Priority:** P1 🎯  
**Effort:** 20-30 hours (phased)  
**Assignee:** Human (strategic) + Jules (implementation)  

---

## 1. Executive Summary

Create graph-enriched CLI wrappers (`mc*`) that mirror OpenAI MCP tools but add:
1. **Schema graph context** — callers, callees, imports, related symbols
2. **LLM-friendly output** — structured hints for what to explore next
3. **Training data generation** — emit OpenAI function-calling format for fine-tuning

**The Key Insight:** Agents should try `mcread` before `read_file`. The enriched version tells them "this file is called by X, imports Y, and you might also want to look at Z" — saving follow-up tool calls.

---

## 2. Architecture: Tool Substitution Pattern

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AGENT TOOL DISPATCH                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Agent wants to read a file                                       │
│           │                                                         │
│           ▼                                                         │
│   ┌───────────────────┐                                            │
│   │ TRY: mcread file  │  ← Graph-enriched (preferred)              │
│   └─────────┬─────────┘                                            │
│             │                                                       │
│             ▼                                                       │
│   ┌───────────────────────────────────────────────────────┐        │
│   │ Output:                                                │        │
│   │   Content: [file content]                              │        │
│   │   Graph Context:                                       │        │
│   │     - Called by: auth.py:validate(), main.py:init()   │        │
│   │     - Imports: utils.py, config.py                     │        │
│   │     - Related: See also auth_middleware.py             │        │
│   └───────────────────────────────────────────────────────┘        │
│                                                                     │
│   FALLBACK (if no graph available):                                │
│   ┌───────────────────┐                                            │
│   │ read_file (raw)   │  ← Standard MCP tool                       │
│   └───────────────────┘                                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Tool Mapping

| mc* CLI | MCP Tool | Graph Enrichment | Status |
|---------|----------|------------------|--------|
| `mcgrep <query>` | `rag_search` | File summaries, span symbols | ✅ DONE |
| `mcwho <symbol>` | `rag_where_used` | Callers, callees, imports graph | ✅ DONE |
| `mcread <file>` | `read_file` | Related files, callers, imports header | 🟡 TODO |
| `mcinspect <symbol>` | `inspect` | Definition + graph neighbors | 🟡 TODO |
| `mcrun <cmd>` | `run_cmd` | Environment context, safety hints | 🟡 TODO |
| `mclist <dir>` | `list_dir` | Connectivity ranking per file | 🔵 LATER |

---

## 4. Implementation: `mcread`

### 4.1 Goal

Replace raw file reads with context-enriched reads.

**Before (raw `read_file`):**
```
$ read_file llmc/router.py
[raw file content, 500 lines]
# Agent has no idea what calls this or what it depends on
```

**After (`mcread`):**
```
$ mcread llmc/router.py

━━━ llmc/router.py ━━━
Purpose: Routes requests to appropriate RAG backends based on file type and query.

Graph Context:
  Called by: llmc/rag/search.py:search_spans (L45)
             llmc_mcp/tools/rag.py:rag_search (L123)
  Imports:   llmc.config, llmc.rag.embeddings, typing
  Exports:   Router (class), route_request (func)
  Related:   llmc/rag/backends/*.py (routed destinations)

[file content with line numbers]
```

### 4.2 Implementation

**File:** `llmc/mcread.py`

```python
#!/usr/bin/env python3
"""
mcread - Read files with graph context.

Like read_file, but tells you what calls it, what it imports, and what to look at next.

Usage:
    mcread llmc/router.py
    mcread llmc/router.py --raw          # No graph enrichment
    mcread llmc/router.py --json         # Structured output
    mcread llmc/router.py --emit-training # OpenAI training format
"""

from pathlib import Path
import typer
from rich.console import Console

from llmc.core import find_repo_root
from llmc.rag.graph import load_graph, get_file_context

console = Console()
app = typer.Typer(name="mcread", help="Read files with graph context.")


@app.command()
def read(
    file_path: str = typer.Argument(..., help="File to read"),
    raw: bool = typer.Option(False, "--raw", help="Skip graph enrichment"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
    emit_training: bool = typer.Option(False, "--emit-training", help="Emit OpenAI training format"),
    start_line: int = typer.Option(None, "-s", "--start", help="Start line (1-indexed)"),
    end_line: int = typer.Option(None, "-e", "--end", help="End line (1-indexed)"),
):
    """Read a file with graph context."""
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)
    
    full_path = repo_root / file_path
    if not full_path.exists():
        console.print(f"[red]File not found:[/red] {file_path}")
        raise typer.Exit(1)
    
    # Read content
    content = full_path.read_text()
    lines = content.splitlines()
    
    # Apply line range if specified
    if start_line or end_line:
        start = (start_line or 1) - 1
        end = end_line or len(lines)
        lines = lines[start:end]
    
    # Get graph context (unless --raw)
    graph_context = None
    if not raw:
        try:
            graph = load_graph(repo_root)
            graph_context = get_file_context(graph, file_path)
        except Exception:
            pass  # Graceful degradation
    
    if emit_training:
        _emit_training_data(file_path, lines, graph_context)
    elif json_output:
        _emit_json(file_path, lines, graph_context)
    else:
        _emit_human(file_path, lines, graph_context)


def _emit_human(file_path: str, lines: list[str], ctx: dict | None):
    """Human-readable output with graph context."""
    console.print(f"[bold cyan]━━━ {file_path} ━━━[/bold cyan]")
    
    if ctx:
        if ctx.get("purpose"):
            console.print(f"[dim]Purpose: {ctx['purpose']}[/dim]\n")
        
        console.print("[bold]Graph Context:[/bold]")
        
        if ctx.get("called_by"):
            console.print("  [green]Called by:[/green]")
            for caller in ctx["called_by"][:5]:
                console.print(f"    {caller['file']}:{caller['symbol']} (L{caller['line']})")
        
        if ctx.get("imports"):
            imports_str = ", ".join(ctx["imports"][:10])
            console.print(f"  [blue]Imports:[/blue] {imports_str}")
        
        if ctx.get("exports"):
            exports_str = ", ".join(ctx["exports"][:10])
            console.print(f"  [yellow]Exports:[/yellow] {exports_str}")
        
        if ctx.get("related"):
            console.print(f"  [magenta]Related:[/magenta] {', '.join(ctx['related'][:3])}")
        
        console.print()
    
    # Print content with line numbers
    for i, line in enumerate(lines, 1):
        console.print(f"[dim]{i:>5}[/dim] │ {line}")


def _emit_json(file_path: str, lines: list[str], ctx: dict | None):
    """JSON output for programmatic use."""
    import json
    output = {
        "file": file_path,
        "content": "\n".join(lines),
        "line_count": len(lines),
        "graph_context": ctx,
    }
    print(json.dumps(output, indent=2))


def _emit_training_data(file_path: str, lines: list[str], ctx: dict | None):
    """Emit OpenAI function-calling training format."""
    import json
    
    # This is what we want models to learn:
    # "When you need to read a file with context, call mcread like this"
    training_example = {
        "messages": [
            {
                "role": "user",
                "content": f"Read the file {file_path} and tell me what it does"
            },
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "mcread",
                            "arguments": json.dumps({"file_path": file_path})
                        }
                    }
                ]
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": json.dumps({
                    "file": file_path,
                    "purpose": ctx.get("purpose") if ctx else None,
                    "called_by": ctx.get("called_by", [])[:3] if ctx else [],
                    "imports": ctx.get("imports", [])[:5] if ctx else [],
                    "content_preview": "\n".join(lines[:20]),
                })
            }
        ]
    }
    print(json.dumps(training_example, indent=2))


def main():
    """Entry point."""
    import sys
    
    # Handle bare file path without 'read' subcommand
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-") and sys.argv[1] != "read":
        sys.argv.insert(1, "read")
    
    app()


if __name__ == "__main__":
    main()
```

### 4.3 Graph Context Helper

**File:** `llmc/rag/graph.py` (add function)

```python
def get_file_context(graph: SchemaGraph, file_path: str) -> dict:
    """Get graph context for a file.
    
    Returns:
        {
            "purpose": str,           # File description if available
            "called_by": [{"file": str, "symbol": str, "line": int}],
            "imports": [str],         # Module names this file imports
            "exports": [str],         # Symbols exported by this file
            "related": [str],         # Related files by graph proximity
        }
    """
    ctx = {
        "purpose": None,
        "called_by": [],
        "imports": [],
        "exports": [],
        "related": [],
    }
    
    # Get file entity
    file_entity = graph.get_entity_by_path(file_path)
    if not file_entity:
        return ctx
    
    # Get purpose from file_descriptions table (if exists)
    ctx["purpose"] = file_entity.get("description")
    
    # Get CALLS edges pointing TO symbols in this file
    for edge in graph.edges:
        if edge.edge_type == "CALLS":
            if edge.dst.startswith(f"file:{file_path}"):
                ctx["called_by"].append({
                    "file": edge.src_file,
                    "symbol": edge.src_symbol,
                    "line": edge.evidence.get("line") if edge.evidence else None,
                })
    
    # Get IMPORTS edges FROM this file
    for edge in graph.edges:
        if edge.edge_type == "IMPORTS" and edge.src_file == file_path:
            ctx["imports"].append(edge.dst_module)
    
    # Get exports (symbols defined in this file)
    for entity in graph.entities:
        if entity.file_path == file_path and entity.kind in ("function", "class"):
            ctx["exports"].append(entity.symbol)
    
    # Get related files by co-occurrence in edges
    related_files = set()
    for edge in graph.edges:
        if edge.src_file == file_path and edge.dst_file:
            related_files.add(edge.dst_file)
        if edge.dst_file == file_path and edge.src_file:
            related_files.add(edge.src_file)
    ctx["related"] = sorted(related_files)[:5]
    
    return ctx
```

---

## 5. Implementation: `mcinspect`

### 5.1 Goal

Inspect a symbol with graph neighbors.

**Before (raw `inspect`):**
```
$ inspect Router
class Router:
    def __init__(self, config): ...
    def route(self, query): ...
```

**After (`mcinspect`):**
```
$ mcinspect Router

━━━ Router (class) ━━━
File: llmc/router.py:15-89
Purpose: Routes queries to appropriate RAG backends.

Definition:
  class Router:
      def __init__(self, config: Config): ...
      def route(self, query: str) -> Backend: ...

Graph Neighbors:
  Callers (3):  search_spans, rag_search, test_router
  Callees (2):  Backend.query, Config.get
  Extends:      (none)
  
See also: mcwho Router (for full caller/callee graph)
```

### 5.2 Implementation

**File:** `llmc/mcinspect.py`

```python
#!/usr/bin/env python3
"""
mcinspect - Inspect symbols with graph context.

Usage:
    mcinspect Router
    mcinspect llmc.router.Router
    mcinspect Router --raw         # Definition only, no graph
"""

from pathlib import Path
import typer
from rich.console import Console

from llmc.core import find_repo_root
from llmc.rag.graph import load_graph, get_symbol_context
from llmc.rag.inspector import inspect_symbol

console = Console()
app = typer.Typer(name="mcinspect", help="Inspect symbols with graph context.")


@app.command()
def inspect(
    symbol: str = typer.Argument(..., help="Symbol to inspect (e.g., Router, llmc.router.Router)"),
    raw: bool = typer.Option(False, "--raw", help="Skip graph enrichment"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Inspect a symbol with graph context."""
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)
    
    # Get symbol definition
    definition = inspect_symbol(repo_root, symbol)
    if not definition:
        console.print(f"[red]Symbol not found:[/red] {symbol}")
        raise typer.Exit(1)
    
    # Get graph context
    graph_context = None
    if not raw:
        try:
            graph = load_graph(repo_root)
            graph_context = get_symbol_context(graph, symbol)
        except Exception:
            pass
    
    if json_output:
        _emit_json(symbol, definition, graph_context)
    else:
        _emit_human(symbol, definition, graph_context)


def _emit_human(symbol: str, defn: dict, ctx: dict | None):
    """Human-readable output."""
    kind = defn.get("kind", "symbol")
    console.print(f"[bold cyan]━━━ {symbol} ({kind}) ━━━[/bold cyan]")
    console.print(f"File: {defn['file']}:{defn['start_line']}-{defn['end_line']}")
    
    if defn.get("docstring"):
        console.print(f"[dim]Purpose: {defn['docstring'][:100]}...[/dim]")
    
    console.print("\n[bold]Definition:[/bold]")
    console.print(f"  {defn['signature']}")
    
    if ctx:
        console.print("\n[bold]Graph Neighbors:[/bold]")
        if ctx.get("callers"):
            callers = ", ".join(ctx["callers"][:5])
            console.print(f"  [green]Callers ({len(ctx['callers'])}):[/green] {callers}")
        if ctx.get("callees"):
            callees = ", ".join(ctx["callees"][:5])
            console.print(f"  [blue]Callees ({len(ctx['callees'])}):[/blue] {callees}")
        if ctx.get("extends"):
            console.print(f"  [yellow]Extends:[/yellow] {ctx['extends']}")
        
        console.print(f"\n[dim]See also: mcwho {symbol} (for full caller/callee graph)[/dim]")


def main():
    import sys
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-") and sys.argv[1] != "inspect":
        sys.argv.insert(1, "inspect")
    app()


if __name__ == "__main__":
    main()
```

---

## 6. AGENTS.md Integration

Once CLIs exist, update AGENTS.md:

```markdown
## Preferred Tools (Graph-Enriched)

Try these first — they return context that saves follow-up calls:

| Tool | When to Use | Example |
|------|-------------|---------|
| `mcgrep "query"` | Semantic search | `mcgrep "authentication flow"` |
| `mcwho symbol` | Find callers/callees | `mcwho Router` |
| `mcread file` | Read file + context | `mcread llmc/router.py` |
| `mcinspect symbol` | Get definition + graph | `mcinspect Router` |

## Fallback Tools (Raw MCP)

Use when graph-enriched tools fail or aren't needed:

| Tool | When to Use |
|------|-------------|
| `read_file` | Exact file read, no context |
| `grep_search` | Literal string search |
| `run_cmd` | Shell commands |
```

---

## 7. Training Data Strategy

Each `mc*` CLI can emit training data:

```bash
# Generate training examples
mcread llmc/router.py --emit-training >> training_corpus.jsonl
mcwho Router --emit-training >> training_corpus.jsonl
mcgrep "auth" --emit-training >> training_corpus.jsonl
```

**Training data format (OpenAI function calling):**
```json
{
  "messages": [
    {"role": "user", "content": "Read llmc/router.py and explain what calls it"},
    {"role": "assistant", "tool_calls": [{"function": {"name": "mcread", "arguments": {"file_path": "llmc/router.py"}}}]},
    {"role": "tool", "content": {"file": "llmc/router.py", "called_by": ["search_spans", "rag_search"], ...}}
  ]
}
```

This teaches models:
1. **Tool selection** — when to use `mcread` vs `read_file`
2. **Argument format** — correct parameter structure
3. **Response interpretation** — how to use graph context

---

## 8. Phased Implementation

| Phase | Deliverable | Effort | Owner |
|-------|-------------|--------|-------|
| 1 | `mcread` with graph header | 8h | Jules |
| 2 | `mcinspect` with neighbors | 6h | Jules |
| 3 | `--emit-training` flag for all CLIs | 4h | Jules |
| 4 | AGENTS.md update | 2h | Human |
| 5 | `mcrun` (later, security considerations) | 6h | Human |

---

## 9. Success Criteria

- [ ] `mcread file` shows graph context header
- [ ] `mcinspect symbol` shows definition + neighbors
- [ ] All `mc*` tools have `--emit-training` flag
- [ ] AGENTS.md directs agents to prefer `mc*` tools
- [ ] Agents successfully use `mcread` instead of `read_file`

---

## 10. Files Created/Modified

| File | Change |
|------|--------|
| `llmc/mcread.py` | New CLI |
| `llmc/mcinspect.py` | New CLI |
| `llmc/rag/graph.py` | Add `get_file_context()`, `get_symbol_context()` |
| `pyproject.toml` | Add entry points |
| `AGENTS.md` | Add preferred tool section |
| `tests/cli/test_mcread.py` | Tests |
| `tests/cli/test_mcinspect.py` | Tests |

---

## 11. Notes

This SDD is **strategic** — it establishes the pattern of "try enriched first, fall back to raw". The training data generation enables fine-tuning local models to prefer these tools without explicit prompting.

**Key Dependency:** Requires graph to be built. Falls back gracefully when unavailable.
