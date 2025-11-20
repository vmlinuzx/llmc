# SDD: `rag inspect` — LLM‑Optimized Context Source Tool

## 1. Goal

Provide a **single, cheap local call** that gives a remote LLM most of what it needs to understand a file or symbol, without running a “codebase investigator” loop.

Primary objective: **optimize LLM usage (tokens + round trips)**, *not* TUI responsiveness.

`rag inspect` should:

- Avoid embedding models entirely.
- Use precomputed **graph** + **enrichment DB**.
- Return:
  - A concise **summary** and **structured relationships**.
  - A **small, focused snippet** of source by default.
  - Optionally the **full file** when explicitly requested.

The TUI will use this as a nerd/debug view, but LLMs (via MCP or CLI) are the main consumers.

---

## 2. Primary Interfaces

### 2.1 Python / Library API (for MCP + local agents)

Core function used by MCP tools and any local LLMC agents:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Literal

SourceMode = Literal["symbol", "file"]

@dataclass
class RelatedEntity:
    symbol: str             # e.g. "tools.rag.search.result_norm_vector"
    path: str               # repo-relative path

@dataclass
class DefinedSymbol:
    name: str               # symbol name
    line: int               # 1-based starting line
    type: str               # "function", "class", "test", "doc-section", etc.
    summary: Optional[str] = None  # from enrichment/docstring if available

@dataclass
class InspectionResult:
    path: str                             # repo-relative path
    source_mode: SourceMode               # "symbol" or "file"

    # Source payload
    snippet: str                          # focused, small snippet (always present)
    full_source: Optional[str]            # only filled if explicitly requested
    primary_span: Optional[tuple[int,int]]  # (start_line, end_line) for the snippet
    file_summary: Optional[str]           # high-level file/symbol summary

    # Structure
    defined_symbols: List[DefinedSymbol]

    parents: List[RelatedEntity]
    children: List[RelatedEntity]
    incoming_calls: List[RelatedEntity]
    outgoing_calls: List[RelatedEntity]
    related_tests: List[RelatedEntity]
    related_docs: List[RelatedEntity]

    enrichment: Dict                      # summary/inputs/outputs/side_effects/pitfalls/evidence_count
    provenance: Dict                      # kind, last_commit, last_commit_date, indexed_at
```

Core function:

```python
def inspect_entity(
    repo_root: Path,
    *,
    symbol: Optional[str] = None,
    path: Optional[str] = None,
    line: Optional[int] = None,
    include_full_source: bool = False,
    max_neighbors: int = 3,
) -> InspectionResult:
    """Resolve a symbol or file location, aggregate graph + enrichment + provenance,
    and return a compact InspectionResult optimized for LLM consumption."""
```

**Resolution priority:**

1. If `symbol` is provided → resolve directly via graph.
2. Else if `path` (+ optional `line`) is provided → resolve entity covering that line, or treat as file-level.
3. If nothing resolves → raise a controlled error or return a minimal error-bearing result.

### 2.2 CLI API (LLM‑friendly & human‑usable)

CLI is mostly for manual use or for LLMs that can only shell out:

```bash
python -m tools.rag.cli inspect \
  --symbol tools.rag.search.result_norm_vector \
  [--json] [--full]

python -m tools.rag.cli inspect \
  --path tools/rag/search.py [--line 140] \
  [--json] [--full]
```

Flags:

- `--symbol` – preferred; symbol-centric use.
- `--path` / `--line` – fallback when you only know the file/line.
- `--json` – machine-readable output (for LLMs).
- `--full` – include full source in `full_source`; text mode prints full file after header.

Text mode output (for humans / quick debugging):

```text
# FILE: tools/rag/search.py
# SOURCE_MODE: symbol
# SYMBOL: tools.rag.search.result_norm_vector
# KIND: code
# SUMMARY: Normalizes a result vector, guarding zero-length inputs.
# DEFINED SYMBOLS:
#   - result_norm_vector (function, line 132)
# RELATIONSHIPS:
#   - Parents: tools.rag.search (module)
#   - Calls: tools.rag.normalize_vector, math.sqrt
#   - Called by: tools.rag.tool_rag_search
#   - Tests: tests/test_rag_search.py::test_result_norm_vector_basic
#   - Docs: DOCS/REPODOCS/tools/rag/search.py.md#result-norm-vector

# SNIPPET (lines 132–160):
def result_norm_vector(...):
    ...
```

---

## 3. Behavior & Token‑Efficiency Rules

### 3.1 Default behavior (LLM‑safe)

When `include_full_source=False` (default):

- `snippet`:
  - Should be **symbol‑focused** when `symbol` can be resolved:
    - From `primary_span`, truncated to a **reasonable line budget** (e.g. 40–80 lines).
  - File‑level:
    - First 80–100 lines, or the most relevant top‑level definition(s).
- `full_source`:
  - MUST be `None` in JSON by default.
- `defined_symbols`:
  - Include a small list of the most important top‑level symbols (limit ~10; can be configurable).
- Relationship lists:
  - Truncate each to `max_neighbors` entries (default 3).

The goal is that a single `inspect_entity` call yields:

- Enough structure + a small snippet for the LLM to decide:
  - “Do I need the full file, or can I reason with this?”
- Without blowing the context window by accident.

### 3.2 Full‑source behavior (opt‑in)

When `include_full_source=True` or `--full` is set:

- `full_source`:
  - Contains the entire file contents.
- `snippet`:
  - Still present, same rules as default.
- Text mode:
  - First header, then entire file contents printed.

This mode is mainly for:

- Local LLMs with large context windows.
- One‑off human debugging (`less`/`vim` readability).

### 3.3 Relationship & enrichment content

- **Parents/children**:
  - Use graph edges (container relationships).
- **Calls/called_by**:
  - Use call‑graph edges.
- **Related tests/docs**:
  - Use `tests` / `documents` edge types.

All relationships should be **symbol + path**, not prose strings, so LLMs can:

- Ask follow‑up questions like “inspect that test symbol”.
- Build their own text around it.

`enrichment` should expose:

```python
enrichment = {
    "summary": str | None,
    "inputs": List[str] | None,
    "outputs": List[str] | None,
    "side_effects": List[str] | None,
    "pitfalls": List[str] | None,
    "evidence_count": int | None,
}
```

If missing, keep keys but use `None` / empty values.

---

## 4. Data Sources & Constraints

### 4.1 No embeddings allowed

- `inspector.py` MUST NOT import or use any embedding/model code.
- It may only use:
  - File I/O
  - Graph access (e.g. `SchemaGraph` reading `.llmc/rag_graph.json` or equivalent)
  - Enrichment DB access (SQLite)
  - Optional git calls

### 4.2 Graph & DB Access

- Graph:
  - Use existing graph access helpers to resolve:
    - symbol → node
    - node → parents/children/calls/tests/docs
    - node/file → spans and defined symbols
- DB:
  - Use existing `.rag/index_v2.db` helper(s) to look up enrichments by span or symbol ID.

Caching:

- For MCP/local agents:
  - It is acceptable (and recommended) to keep graph + DB handles **alive** across calls.
- For CLI:
  - One‑shot process is fine; performance is secondary compared to LLM savings.

### 4.3 Provenance

Populate a lightweight `provenance` dict:

```python
provenance = {
    "kind": str | None,             # "code", "test", "docs", "config", etc.
    "last_commit": str | None,      # short SHA
    "last_commit_date": str | None, # e.g. "2025-11-18"
    "indexed_at": str | None,       # index timestamp if available
}
```

- `kind`:
  - Based on path prefixes (`tests/`, `DOCS/`, etc.) or graph metadata.
- Git:
  - Use `git log -1 --format="%h %cs" -- <path>` when available.
  - If git is not available, set fields to `None`, do not raise.

---

## 5. TUI Usage (Secondary Concern)

The TUI is **not** performance‑critical; it just reuses this tool.

- Add keybinding `i` in the search screen:
  - On selected result, call `inspect_entity` (or the CLI version) and render:
    - Summary
    - Relationships
    - Snippet
- It’s acceptable if this takes ~1s+; human latency is not the bottleneck.

The TUI is effectively a **visualizer** of what the LLM sees via `rag inspect`.

---

## 6. Test Strategy

New test module: `tests/test_rag_inspect_llm_tool.py`.

### 6.1 `test_inspect_entity_symbol_default_snippet`

- Create a small file with a function and symbol in the graph.
- Call `inspect_entity(..., symbol="...")` with defaults.
- Assert:
  - `source_mode == "symbol"`.
  - `snippet` is non‑empty and **shorter** than full file.
  - `full_source is None`.
  - `primary_span` describes a reasonable range.

### 6.2 `test_inspect_entity_file_default_snippet`

- Call `inspect_entity(..., path="path/to/file.py")` with no symbol.
- Assert:
  - `source_mode == "file"`.
  - `snippet` corresponds to the beginning or key definitions of the file.
  - `defined_symbols` is populated with at least one symbol.

### 6.3 `test_inspect_entity_full_source_flag`

- Call `inspect_entity(..., path="...", include_full_source=True)`.
- Assert:
  - `full_source` equals on‑disk contents.
  - `snippet` still present.

### 6.4 `test_inspect_entity_relationships_truncated`

- Construct/mutate a small graph with many callers/callees.
- Call `inspect_entity(..., max_neighbors=3)`.
- Assert:
  - Each relationship list length is `<= 3`.

### 6.5 `test_inspect_entity_enrichment_fields`

- Mock enrichment db to return:
  - `summary`, `inputs`, `outputs`, `side_effects`, `pitfalls`, `evidence_count`.
- Assert that `enrichment` dict mirrors those values correctly.

### 6.6 `test_inspect_entity_no_graph_or_db`

- Configure environment so graph + DB return no data.
- Call `inspect_entity(..., path="...")`.
- Assert:
  - `snippet` is still populated.
  - Relationship lists are empty, no exceptions raised.

### 6.7 `test_cli_inspect_json`

- `subprocess.run(["python", "-m", "tools.rag.cli", "inspect", "tools/rag/cli.py", "--json"])`
- Assert:
  - Exit code 0.
  - JSON parses and has keys: `path`, `snippet`, `source_mode`, `enrichment`, `provenance`.

### 6.8 `test_cli_inspect_text_header`

- Call CLI without `--json`.
- Assert:
  - Output starts with `# FILE:`.
  - Contains `# SNIPPET` or similar marker.
  - Does not dump full file unless `--full` is used.

---

## 7. Implementation Steps

1. **Implement library API** in `tools/rag/inspector.py`:
   - `RelatedEntity`, `DefinedSymbol`, `InspectionResult`.
   - `inspect_entity(...)` with symbol/file resolution, snippet generation, graph + DB queries, provenance.
2. **Wire CLI** in `tools/rag/cli.py`:
   - `inspect` command with `--symbol`, `--path`, `--line`, `--json`, `--full`.
   - Text + JSON output modes.
3. **Add MCP tool (optional next patch)**:
   - Expose `inspect_entity` as an MCP method (e.g. `rag.inspect_entity`) for remote LLMs.
4. **Write tests** in `tests/test_rag_inspect_llm_tool.py` and adjust fixtures as needed.
5. **Manual check**:
   - Call CLI for a few key symbols/files and verify:
     - Small snippet.
     - Reasonable relationships.
     - Enrichment summary when present.
6. **Update docs**:
   - Brief section in your LLMC tooling docs describing `rag inspect` as the “LLM‑optimized context source tool” and how agents should use it instead of multi‑step repo spelunking.