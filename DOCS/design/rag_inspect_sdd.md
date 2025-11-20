# SDD: `rag inspect` — Context-Aware Source Reader

## 1. Goal
Create a low-latency CLI tool that acts as a "Super Read" for LLMs. It returns the **source code** of a file augmented with pre-computed **graph relationships** (callers, callees, tests) and **enrichment data** (summaries, pitfalls). This avoids using the slow embedding model and replaces the expensive "Codebase Investigator" agent for file-level understanding.

## 2. Architecture

### 2.1 New Module: `tools/rag/inspector.py`
A new pure-logic module (no heavyweight ML imports) responsible for aggregating data.

**Data Structures:**
```python
@dataclass
class InspectionResult:
    path: str
    source_code: str
    file_summary: Optional[str]
    defined_symbols: List[Dict]  # {name, line, summary, type}
    incoming_calls: List[str]    # "X calls Y" summary
    outgoing_calls: List[str]    # "Y calls Z" summary
    related_tests: List[str]     # List of test files/symbols
    provenance: Dict             # Last commit, modification time
```

**Core Function:**
```python
def inspect_file(repo_root: Path, target_path: str) -> InspectionResult:
    """
    1. Resolve target_path to an absolute file path.
    2. Read raw source code.
    3. Load .llmc/rag_graph.json (if cached) to find graph edges.
    4. Query .rag/index_v2.db (sqlite) for enrichment metadata.
    5. Aggregate and return.
    """
```

### 2.2 CLI Update: `tools/rag/cli.py`
Add a new command that exposes this logic.

```python
@cli.command()
@click.argument("path")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON")
def inspect(path: str, as_json: bool):
    """
    Fast look up of a file with added context (Graph + Enrichment).
    Does NOT load embedding models (instant execution).
    """
```

### 2.3 Output Format (Text Mode)
Designed for LLM consumption (concise header + content).

```text
# FILE: tools/rag/inspector.py
# CONTEXT:
#   - Defined Symbols: inspect_file (func), InspectionResult (class)
#   - Related Tests: tests/test_rag_inspector.py
#   - Used By: tools/rag/cli.py
#   - Summary: Aggregates graph and DB data for fast inspection.

<... Raw Source Code ...>
```

## 3. Test Strategy

We will create `tests/test_rag_inspector.py` containing:

1.  **`test_inspect_basic_file`**:
    *   Create a temp file `hello.py`.
    *   Run `inspect_file`.
    *   Assert `source_code` matches.

2.  **`test_inspect_with_mock_graph`**:
    *   Mock `SchemaGraph.load` to return a graph where `hello.py` is called by `main.py`.
    *   Run `inspect_file`.
    *   Assert `incoming_calls` contains `main.py`.

3.  **`test_inspect_with_mock_db`**:
    *   Mock `Database` to return a summary "Greets the world" for `hello.py`.
    *   Run `inspect_file`.
    *   Assert `file_summary` matches.

4.  **`test_cli_integration`**:
    *   Run `python -m tools.rag.cli inspect tools/rag/cli.py`.
    *   Ensure it exits 0 and output contains source code.

## 4. Implementation Steps

1.  **Create Test**: Write `tests/test_rag_inspector.py` with failing tests (TDD).
2.  **Implement Logic**: Create `tools/rag/inspector.py`.
    *   Implement `SchemaGraph` partial loader (or use existing if fast enough).
    *   Implement SQLite lookups.
3.  **Implement CLI**: Add command to `tools/rag/cli.py`.
4.  **Verify**: Run tests and manually check speed.

## 5. Constraints & Risks
*   **Graph Size**: `rag_graph.json` can get large. `inspector.py` should try to lazy-load or use the existing `SchemaGraph` class if it's optimized enough. (It is just JSON load, should be <100ms for moderate repos).
*   **Resolution**: Users might pass partial paths (`cli.py` vs `tools/rag/cli.py`). The resolver must be smart (use `fuzzy_find` logic or simple suffix match).