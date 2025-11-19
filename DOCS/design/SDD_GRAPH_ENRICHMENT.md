# SDD: Phase 2 - Graph Enrichment (Database to SchemaGraph Integration)

## 1. Introduction
This Software Design Document details the implementation plan for integrating enrichment data from the SQLite database into the `SchemaGraph`, as outlined in `HLD_GRAPH_ENRICHMENT.md`. The primary goal is to enhance the `SchemaGraph` entities with semantic metadata derived from LLM analysis, making the graph a richer source of context for RAG tools.

## 2. Refined Problem Statement
The high-level problem is the disjunction between structural code understanding and semantic enrichment. Specifically, the technical challenges include:
*   **Entity-to-Record Matching**: Precisely linking an `SchemaGraph.Entity` (which has `file_path`, `start_line`, `end_line`, `span_hash`) to one or more `EnrichmentRecord`s (which also have `file_path` and `span_hash` or line ranges).
*   **Metadata Schema**: Defining a flexible, queryable, and version-controlled schema for the enrichment metadata to be stored within `SchemaGraph.Entity` objects.
*   **Merging Logic**: Developing a robust strategy for combining multiple enrichment records that might apply to a single graph entity, or for handling conflicts.
*   **Performance**: Ensuring the enrichment lookup and merging process does not significantly degrade the graph build time, especially for large codebases.

## 3. Detailed Design

### 3.1 Schema Changes (`tools.rag.schema`)

We will modify the `Entity` dataclass in `tools/rag/schema.py` to include a `metadata` field:

```python
# tools/rag/schema.py
from typing import Dict, Any, Optional

@dataclass
class Entity:
    id: str
    name: str
    type: str
    file_path: str
    start_line: int
    end_line: int
    span_hash: str
    # ... other existing fields ...
    metadata: Dict[str, Any] = field(default_factory=dict) # New field
```
*   **`metadata` field**: A dictionary to store various key-value pairs of enrichment data. This provides extensibility without requiring schema migrations for every new type of enrichment.

### 3.2 Enrichment Database Helpers (`tools.rag.enrichment_db_helpers`)

A new module `tools/rag/enrichment_db_helpers.py` will be created to encapsulate SQLite interactions for fetching enrichment data.

```python
# tools/rag/enrichment_db_helpers.py
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class EnrichmentRecord:
    # Matches structure of 'enrichments' table and relevant 'spans' columns
    span_hash: str
    file_path: str
    start_line: int
    end_line: int
    summary: Optional[str] = None
    usage_guide: Optional[str] = None
    # Add other fields as needed from enrichment process

def get_enrichment_db_path(repo_root: Path) -> Path:
    """Returns the path to the enrichment database for a given repo."""
    # Assumes a standard location, e.g., repo_root / ".llmc" / "rag" / "enrichment.db"
    return repo_root / ".llmc" / "rag" / "enrichment.db"

def load_enrichment_data(repo_root: Path) -> Dict[str, List[EnrichmentRecord]]:
    """
    Loads all enrichment data from the SQLite DB for a repo.
    Returns a dict mapping span_hash to a list of EnrichmentRecords.
    """
    db_path = get_enrichment_db_path(repo_root)
    if not db_path.exists():
        return {}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row # Access columns by name
    cursor = conn.cursor()

    # Query the 'enrichments' table. Join with 'spans' if needed for line numbers etc.
    # For now, assume 'enrichments' table has span_hash, file_path, start_line, end_line, summary, usage_guide
    cursor.execute("""
        SELECT span_hash, file_path, start_line, end_line, summary, usage_guide
        FROM enrichments
        -- ORDER BY created_at DESC -- if we care about freshness/priority
    """)
    
    enrichments_by_span: Dict[str, List[EnrichmentRecord]] = {}
    for row in cursor.fetchall():
        record = EnrichmentRecord(**dict(row))
        if record.span_hash not in enrichments_by_span:
            enrichments_by_span[record.span_hash] = []
        enrichments_by_span[record.span_hash].append(record)

    conn.close()
    return enrichments_by_span

```
*   **`EnrichmentRecord`**: A dataclass to represent a single piece of enrichment.
*   **`load_enrichment_data`**: Optimized to load all data into memory for efficient lookup during graph traversal. The key is `span_hash` as it's the most reliable unique identifier for a span.

### 3.3 Graph Enrichment Logic (`tools.rag_nav.tool_handlers`)

The main logic for enriching the graph will be added to `tools/rag_nav/tool_handlers.py`. The existing `build_graph_for_repo` function will be extended or a new function will be introduced to perform this step.

```python
# tools/rag_nav/tool_handlers.py (conceptual additions/modifications)
from tools.rag.enrichment_db_helpers import load_enrichment_data, EnrichmentRecord
from tools.rag.schema import SchemaGraph, Entity # Assuming SchemaGraph holds a list of Entities

def build_enriched_schema_graph(repo_root: Path) -> SchemaGraph:
    """
    Builds the SchemaGraph and enriches its entities with data from the
    enrichment database.
    """
    # 1. Build the base structural graph (reusing existing logic)
    #    (This might be a call to an internal function or loading an intermediate artifact)
    base_graph = _build_base_structural_schema_graph(repo_root) # Existing logic

    # 2. Load all enrichment data
    enrichments_by_span = load_enrichment_data(repo_root)

    # 3. Iterate through graph entities and merge metadata
    for entity in base_graph.entities: # Assuming SchemaGraph has an 'entities' attribute
        # Primary matching key: span_hash
        if entity.span_hash in enrichments_by_span:
            # Conflict Resolution Strategy: For now, take the first record.
            # SDD TODO: Refine this. For example, merge all records as a list,
            # or apply specific prioritization rules based on enrichment type.
            matched_records = enrichments_by_span[entity.span_hash]

            # Current strategy: simple merge of summary and usage_guide directly to entity.metadata
            # Future: structured metadata. For now, flat.
            for record in matched_records:
                if record.summary:
                    entity.metadata["summary"] = record.summary
                if record.usage_guide:
                    entity.metadata["usage_guide"] = record.usage_guide
                # Add other fields from EnrichmentRecord to metadata as needed
            
            # Alternative (more flexible) structure:
            # entity.metadata["enrichments"] = [asdict(r) for r in matched_records]
            # Decision for this made in SDD below.

    # 4. Save the enriched graph
    _save_schema_graph(repo_root, base_graph) # Existing logic or new save function
    return base_graph

# Internal helper (if not already exposed)
def _build_base_structural_schema_graph(repo_root: Path) -> SchemaGraph:
    """Loads/builds the purely structural graph from AST analysis."""
    # Placeholder for actual graph building/loading logic
    pass

def _save_schema_graph(repo_root: Path, graph: SchemaGraph):
    """Saves the SchemaGraph to disk."""
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    with open(graph_path, "w") as f:
        json.dump(asdict(graph), f, indent=2)
```
*   **Matching Strategy**:
    *   Primary: `span_hash`. This is the most robust and stable identifier for a code span across minor code changes.
    *   Fallback (SDD TO-DO): If `span_hash` is not available or unique, consider matching by `file_path` + (`start_line`, `end_line`) with a tolerance for minor line shifts. This adds complexity and will be deferred for now.

*   **Metadata Merging Logic**:
    *   For this phase, a simple merging will be implemented: directly assigning `summary` and `usage_guide` from the `EnrichmentRecord` into the `entity.metadata` dictionary, overwriting if multiple records provide the same key (e.g., `summary`).
    *   **Refinement**: `entity.metadata` will be a dictionary where keys map to enrichment types (e.g., `"summary"`, `"usage_guide"`). If multiple `EnrichmentRecord`s exist for a `span_hash`, the most recent one (if available, otherwise first) will be used for each distinct metadata key.

### 3.4 Command Line Interface (CLI) Integration

The `llmc-rag-nav build-graph --repo .` command will be updated to call `build_enriched_schema_graph`.

```bash
# llmc-rag-nav build-graph --repo .
# This command will now trigger the enrichment process.
```

### 3.5 Error Handling
*   **Missing Enrichment DB**: If `load_enrichment_data` cannot find the DB, it will return an empty dictionary, resulting in an unenriched graph. This is a graceful degradation.
*   **Corrupt Enrichment DB**: If `load_enrichment_data` encounters a corrupt DB, it should log the error and return an empty dictionary. The graph building process should continue, producing an unenriched graph.
*   **Partial Matches**: If an entity has no matching `span_hash` in the enrichment data, its `metadata` field will remain empty or unchanged. This is expected behavior.

## 4. Specific Test Cases (from HLD Test Strategy)

### 4.1 Unit Tests

*   **`tools/rag/enrichment_db_helpers.py`**:
    *   **Test Case 1.1: Load from empty/non-existent DB**: Call `load_enrichment_data` with a non-existent DB path; assert an empty dictionary is returned.
    *   **Test Case 1.2: Load from valid DB**: Create a temporary DB with a known `EnrichmentRecord`; call `load_enrichment_data`; assert the correct `EnrichmentRecord` is returned mapped to its `span_hash`.
    *   **Test Case 1.3: Load with multiple records for one span**: Create a temporary DB with two `EnrichmentRecord`s for the same `span_hash`; assert both are returned in a list.
    *   **Test Case 1.4: Load with corrupt DB**: Create a corrupt DB file; assert `load_enrichment_data` logs an error and returns an empty dictionary.

### 4.2 Integration Tests

*   **"Happy Path"**:
    *   **Test Case 2.1: Full Enrichment**:
        1.  Create a temporary repo with a simple Python file (`test_module.py` with `def example_func():`).
        2.  Create a mock enrichment DB (`enrichment.db`) with an `EnrichmentRecord` matching `example_func`'s `span_hash`, including `summary` and `usage_guide`.
        3.  Run `build_enriched_schema_graph` for the repo.
        4.  Load the resulting `rag_graph.json`.
        5.  Assert that `example_func`'s `Entity` in the graph has `metadata` containing the correct `summary` and `usage_guide`.
*   **"No Enrichment"**:
    *   **Test Case 2.2: Graph without Enrichment DB**:
        1.  Create a temporary repo with a simple Python file.
        2.  Ensure no `enrichment.db` exists.
        3.  Run `build_enriched_schema_graph`.
        4.  Load `rag_graph.json`.
        5.  Assert all `Entity` objects have an empty `metadata` dictionary.
*   **"Partial Enrichment"**:
    *   **Test Case 2.3: Some Entities Enriched**:
        1.  Create a temporary repo with two Python functions (`func_a`, `func_b`).
        2.  Create an `enrichment.db` with an `EnrichmentRecord` only for `func_a`.
        3.  Run `build_enriched_schema_graph`.
        4.  Load `rag_graph.json`.
        5.  Assert `func_a`'s `Entity` has `metadata` populated, and `func_b`'s `Entity` has empty `metadata`.
*   **"DB Unavailable/Corrupt"**:
    *   **Test Case 2.4: Corrupt Enrichment DB during build**:
        1.  Create a temporary repo and a corrupt `enrichment.db`.
        2.  Run `build_enriched_schema_graph`.
        3.  Assert the graph is built (unenriched) and an error is logged.
*   **Golden File Regression**:
    *   **Test Case 2.5: Structural Integrity**:
        1.  Use a known structural `rag_graph.json` fixture.
        2.  Run `build_enriched_schema_graph` (even without enrichment data).
        3.  Assert the resulting `rag_graph.json` perfectly matches the structural fixture (except for the added `metadata` field, which should be empty). This confirms no existing graph data is inadvertently altered.

## 5. Data Structures
### 5.1 `SchemaGraph.Entity` Metadata
```python
# Conceptual structure within Entity.metadata
{
    "summary": "str (concise LLM summary of the entity)",
    "usage_guide": "str (LLM-generated guide on how to use the entity)",
    "inputs": "Dict[str, str] (e.g., {'arg1': 'description'})",
    "outputs": "Dict[str, str] (e.g., {'return_val': 'description'})",
    "pitfalls": "List[str] (e.g., ['Potential for off-by-one errors'])",
    "side_effects": "List[str] (e.g., ['Modifies global state'])",
    "related_concepts": "List[str] (e.g., ['authentication', 'session management'])"
    # ... extensible with other enrichment types
}
```
*   **Default Merging**: For `summary` and `usage_guide`, the value from the *first* `EnrichmentRecord` (or most recent, if `created_at` ordering is implemented) will be used.
*   **Complex fields**: For fields like `pitfalls` or `side_effects` which could be lists, they will be appended to ensure no loss of information from multiple records.

## 6. Performance Considerations
*   Loading all enrichment data at once (`load_enrichment_data`) is efficient for lookup if the enrichment DB is not excessively large.
*   Querying by `span_hash` is fast due to indexing.
*   The primary bottleneck will be the initial structural graph generation, which is outside the scope of this SDD. The enrichment step adds linear overhead proportional to the number of entities and enrichment records.

## 7. Future Considerations (Out of Scope for this SDD)
*   **Incremental Enrichment**: Updating only changed entities without rebuilding the entire graph.
*   **Cross-Repo Enrichment**: Merging enrichment from multiple repositories.
*   **Advanced Conflict Resolution**: More sophisticated merging strategies for conflicting enrichment data.
*   **Enrichment Versioning**: Storing multiple versions of enrichment for an entity.

## 8. Development Tasks
1.  Update `tools/rag/schema.py` to add `metadata: Dict[str, Any]` to `Entity`.
2.  Create `tools/rag/enrichment_db_helpers.py` with `EnrichmentRecord` and `load_enrichment_data`.
3.  Modify `tools/rag_nav/tool_handlers.py` to implement `build_enriched_schema_graph` and integrate `load_enrichment_data`.
4.  Update `llmc-rag-nav build-graph` CLI command to call `build_enriched_schema_graph`.
5.  Implement all specified unit and integration tests.
6.  Update relevant documentation and examples.
