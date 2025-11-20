# SDD: `rag inspect` — Context-Aware Source Reader

## 1. Goal

Create a low-latency CLI + library tool that acts as a **"Context-Aware Source Reader"** for LLMs and the LLMC TUI. It returns the **source code** of a file, augmented with:

- Pre-computed **graph relationships** (parents, children, callers, callees, related tests/docs).
- **Enrichment data** (summaries, inputs/outputs, pitfalls).
- Basic **provenance** (kind, last commit, index timestamp).

This tool must **not** load any embedding models and should be fast enough to feel “instant” when invoked from the TUI (sub-200ms on a warm process).

It partially replaces the expensive “Codebase Investigator” behavior at the file/symbol level by leveraging LLMC’s existing RAG graph and enrichment DB.

---

## 2. Architecture

### 2.1 New Module: `tools/rag/inspector.py`

A new pure-logic module (no heavyweight ML imports) responsible for aggregating data about a file/symbol.

#### 2.1.1 Data Structures

Use a structured result type instead of strings so both the TUI and LLM tools can consume it.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

@dataclass
class RelatedEntity:
    symbol: str          # e.g. "tools.rag.search.result_norm_vector"
    path: str            # repo-relative path, e.g. "tools/rag/search.py"

@dataclass
class DefinedSymbol:
    name: str            # symbol name
    line: int            # 1-based starting line in file
    type: str            # "function", "class", "test", "doc-section", etc.
    summary: Optional[str] = None  # from enrichment or docstring

@dataclass
class InspectionResult:
    path: str                             # repo-relative path
    source_code: str                      # full file contents
    preview: str                          # short snippet/preview
    file_summary: Optional[str]           # high-level summary if available

    defined_symbols: List[DefinedSymbol]

    parents: List[RelatedEntity]          # containers (modules, sections)
    children: List[RelatedEntity]         # nested entities

    incoming_calls: List[RelatedEntity]   # callers in graph
    outgoing_calls: List[RelatedEntity]   # callees in graph
    related_tests: List[RelatedEntity]    # tests that touch this file/symbol
    related_docs: List[RelatedEntity]     # docs that describe this file/symbol

    enrichment: Dict                      # summary/inputs/outputs/side_effects/pitfalls/evidence_count
    provenance: Dict                      # kind, last_commit, last_commit_date, indexed_at
```

Lists should be truncated to a small number of entries (e.g. first 3) for performance and readability in the TUI.

#### 2.1.2 Core Function

```python
def inspect_file(
    repo_root: Path,
    target_path: str,
    symbol: Optional[str] = None,
) -> InspectionResult:
    """Resolve file/symbol, read source, enrich with graph + DB + provenance, and return an InspectionResult."""
```

Key steps (implementation detail):

1. Resolve `target_path` to a repo-relative, normalized path.
2. Read raw source code from disk (full file).
3. Generate a preview snippet (first N lines or the main symbol’s definition).
4. Load graph & DB via existing lightweight helpers (no embedding models).
5. Resolve either:
   - the whole file, or
   - a specific symbol within that file (if `symbol` provided).
6. Aggregate:
   - defined symbols
   - parents/children/calls/called_by/tests/docs
   - enrichment data
   - provenance (kind, last commit, index metadata)
7. Return `InspectionResult`.

**Important constraints:**

- `inspector.py` MUST NOT import any embedding/model code.
- It SHOULD use existing graph/DB access layers (e.g. `SchemaGraph`, DB helpers) that are relatively cheap.
- When used in a long-lived process (TUI/daemon), graph/DB objects SHOULD be cached and reused to avoid repeated JSON/SQLite opens.

### 2.2 CLI Update: `tools/rag/cli.py`

Add a new command that exposes this logic.

```python
@cli.command()
@click.argument("path")
@click.option("--symbol", help="Optional symbol within the file to focus on")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON")
@click.option(
    "--full",
    "full_source",
    is_flag=True,
    help="Emit full source in text mode (otherwise preview only)",
)
def inspect(path: str, symbol: Optional[str], as_json: bool, full_source: bool):
    """Fast inspection of a file (and optionally a symbol) with graph + enrichment context.

    This command MUST NOT load any embedding models. It uses only precomputed
    graph + DB data and direct file reads, so it should be near-instant on a warm process.
    """
```

#### 2.2.1 CLI Behavior

- Resolve `path` relative to `repo_root`.
- Call `inspect_file(repo_root, path, symbol=symbol)`.
- If `--json`:
  - Serialize `InspectionResult` to a JSON object:
    - Nested dicts/lists mirroring the dataclasses.
- If not `--json`:
  - Print a concise, LLM-friendly text header and either:
    - Full source if `--full` is set, OR
    - A preview snippet (first N lines) otherwise.

Example text output:

```text
# FILE: tools/rag/inspector.py
# KIND: code
# SUMMARY: Aggregates graph and DB data for fast inspection.
# DEFINED SYMBOLS:
#   - InspectionResult (class, line 10)
#   - inspect_file (function, line 40)
# RELATIONSHIPS:
#   - Parents: tools.rag (module)
#   - Related tests: tests/test_rag_inspector.py
#   - Used by: tools/rag/cli.py

<preview or full source here>
```

---

## 3. TUI Integration

### 3.1 Trigger / UX

On the LLMC search screen:

- Navigation: results list in the center, Details pane on the right.
- New keybinding: **`i`** for “Inspect”.

Behavior when the user presses `i`:

1. Take the **selected search result**:
   - `path` (repo-relative).
   - optional `symbol` if the search result has one.
2. Call one of:
   - Direct Python: `inspect_file(repo_root, path, symbol)` if the TUI runs in the same process, OR
   - CLI: `python -m tools.rag.cli inspect <path> --symbol <symbol> --json`.
3. Parse the resulting JSON into an `InspectionResult`-like object.
4. Render an enhanced Details pane using:

   ```text
   FILE: <path>
   Symbol: <symbol or "(file)">
   Kind: <provenance.kind>

   Summary:
     <file_summary or enrichment.summary>

   Defined symbols:
     - <name> (<type>, line N) ...

   Graph:
     Parents:   a, b
     Children:  c
     Calls:     d, e
     Called by: f
     Tests:     t1, t2
     Docs:      d1

   Preview:
     <preview snippet>
   ```

Notes:

- Respect terminal width; wrap lines.
- Hide sections that are completely empty to avoid visual noise.
- The inspector becomes the **single source of truth** for relationships/enrichment/provenance in the Details pane.

---

## 4. Resolution & Data Sources

### 4.1 Path Resolution

- `inspect_file` should:
  - Accept both absolute and repo-relative `target_path`.
  - Normalize to a repo-relative path under `repo_root`.
- If the file does not exist:
  - Raise a controlled error or provide a structured failure mode.

### 4.2 Graph Access

- Use the existing graph representation (e.g. `.llmc/rag_graph.json` via `SchemaGraph` or equivalent).
- For a given file:
  - Collect all entities whose `file_path` matches.
  - When `symbol` is provided, filter to that symbol; otherwise, treat the file holistically.
- Extract:
  - `defined_symbols` (name, type, span, optional summary).
  - Parent/child relationships.
  - Calls/called_by edges.
  - Test/document relationships (based on edge types).

All relationship lists should be truncated (e.g. max 3 entries) to keep the TUI readable.

### 4.3 Enrichment Access

- Use the `.rag/index_v2.db` enrichment DB or existing helper.
- For the selected file or symbol:
  - Look up an enrichment record by span or symbol ID.
- Map DB columns → `enrichment` dict:

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

If enrichment is missing, keep keys present but leave values as `None` / empty.

### 4.4 Provenance

- Determine `kind` (`code`, `test`, `docs`, `config`, etc.) based on:
  - File path patterns (e.g. `tests/`, `DOCS/`).
  - Or metadata from the graph.
- Last commit data:
  - Use a lightweight git call such as:
    - `git log -1 --format="%h %cs" -- <path>`
  - Parse into `last_commit` and `last_commit_date`.
- Index timestamp:
  - If RAG metadata tables exist for per-file/index timestamps, populate `indexed_at`.
  - Otherwise, leave `indexed_at` as `None`.

Example:

```python
provenance = {
    "kind": "code",
    "last_commit": "3a9f2c1",
    "last_commit_date": "2025-11-18",
    "indexed_at": "2025-11-19T03:14:00Z",
}
```

---

## 5. Test Strategy

New test module: `tests/test_rag_inspector.py`.

### 5.1 `test_inspect_basic_file`

- Create or use a small test file in a fixture repo.
- Run `inspect_file(repo_root, "path/to/file.py")`.
- Assert:
  - `result.path` matches.
  - `result.source_code` contains expected content.
  - `result.preview` is non-empty and is a prefix of `source_code`.

### 5.2 `test_inspect_with_mock_graph`

- Mock or construct a minimal graph:
  - A function in `hello.py`.
  - A caller in `main.py` with an edge `main -> hello`.
- Run `inspect_file`.
- Assert:
  - `incoming_calls` contains a `RelatedEntity` with `path == "main.py"`.
  - `defined_symbols` contains the function in `hello.py`.

### 5.3 `test_inspect_with_mock_enrichment`

- Mock enrichment DB access to return:
  - `summary = "Greets the world"`.
  - `evidence_count = 1`.
- Run `inspect_file`.
- Assert:
  - `result.enrichment["summary"] == "Greets the world"`.

### 5.4 `test_inspect_without_graph_or_db`

- Configure the environment so graph/DB loaders return “no data” (e.g. missing files or empty structures).
- Run `inspect_file`.
- Assert:
  - `source_code` and `preview` are populated.
  - Relationship lists (`incoming_calls`, `related_tests`, etc.) are empty.
  - No exceptions are raised.

### 5.5 `test_cli_integration_json`

- Use `subprocess.run` to call:

  ```bash
  python -m tools.rag.cli inspect tools/rag/cli.py --json
  ```

- Assert:
  - Exit code 0.
  - JSON parses and has keys: `path`, `source_code`, `preview`, `enrichment`, `provenance`.

### 5.6 `test_cli_integration_text_mode`

- Run:

  ```bash
  python -m tools.rag.cli inspect tools/rag/cli.py
  ```

- Assert:
  - Exit code 0.
  - Output contains `# FILE:` header and a snippet of the file.

---

## 6. Implementation Steps

1. **Create tests** in `tests/test_rag_inspector.py` (failing initially).
2. **Implement `tools/rag/inspector.py`**:
   - Define `RelatedEntity`, `DefinedSymbol`, and `InspectionResult`.
   - Implement `inspect_file(repo_root, target_path, symbol=None)` with graph/DB/provenance plumbing.
3. **Wire into `tools/rag/cli.py`**:
   - Add `inspect` command using `inspect_file`.
   - Support `--json` and `--full` flags.
4. **Integrate with the TUI**:
   - Add `i` keybinding to call `inspect` for the current result.
   - Render enhanced Details pane based on `InspectionResult`.
5. **Run tests and manual smoke checks**:
   - `pytest tests/test_rag_inspector.py`
   - TUI: perform a search, select a result, hit `i`, verify Details updates.

---

## 7. Constraints & Risks

- **Graph size**:
  - `rag_graph.json` may be large. Inspector must rely on existing optimized graph loaders and avoid re-loading graph/DB on every call in long-lived contexts (cache in process).
- **Path resolution**:
  - Start simple (require repo-relative paths). Smarter fuzzy path matching can be added in a later patch.
- **Symbol-level inspection**:
  - `symbol` parameter is included for future symbol-level inspection. Initial implementation may ignore it or only support basic matching.
- **Git dependency**:
  - Provenance uses git; behavior should degrade gracefully if git is unavailable (e.g. set fields to `None` instead of raising).
