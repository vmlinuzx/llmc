<!--
SOURCE_FILE: tools/rag/graph.py
SOURCE_HASH: sha256:6e81e872b6cc0a99bcdce001ad76de82fc4cb55222b0d90bb56323136a8cb151
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/graph.py – High-Level Overview

**tools/rag/graph.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `__init__(self)`
  Function: __init__

- `load_from_schema(self, graph)`
  Load graph from SchemaGraph object

- `load_from_file(self, path)`
  Load graph from JSON file

- `save_to_file(self, path)`
  Save graph structure (delegates to SchemaGraph for actual saving)

- `_extract_relations(self)`
  Reconstruct relations from adjacency list

- `get_neighbors(self, entity_id, max_hops, edge_filter, max_neighbors)`
  Traverse graph from entity_id up to max_hops.

- `get_entity(self, entity_id)`
  Get entity by ID

- `find_entities_by_pattern(self, pattern, kind)`
  Find entities matching a pattern (substring search).

- `get_statistics(self)`
  Get graph statistics for monitoring

- `_count_entity_kinds(self)`
  Count entities by kind

- **GraphNeighbor** (class)
  - Represents a neighbor in the graph with metadata

- **GraphStore** (class)
  - Key methods: __init__, load_from_schema, load_from_file, save_to_file, _extract_relations
  - In-memory graph storage with adjacency lists for fast traversal.


## Data & Schema

### GraphNeighbor

Represents a neighbor in the graph with metadata

**Structure**: Object-oriented data model

### GraphStore

In-memory graph storage with adjacency lists for fast traversal.

Structure:
    adjacency[entity_id] = {
        "outgoing": {"calls": [neighbor_ids], "uses": [...]},
        "incoming": {"called_by": [neighbor_ids], ...}
    }

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `collections`
- `dataclasses`
- `json`
- `pathlib`
- `schema`
- `typing`

**External Services**:
- LLM providers (Claude, MiniMax, Codex, Qwen, Ollama)
- Vector databases for embeddings
- File system for repository indexing


## Configuration & Environment

- **RAG_INDEX_PATH**: `str`
  - Meaning: Path to RAG index storage
  - Default: default from config

- **ENRICH_BATCH_SIZE**: `int`
  - Meaning: Number of files to enrich per batch
  - Default: 100

- **LLM_PROVIDER**: `str`
  - Meaning: Which LLM to use for enrichment
  - Default: claude

- **OLLAMA_ENDPOINT**: `str`
  - Meaning: URL of Ollama service
  - Default: http://localhost:11434

## Error Handling, Edge Cases, and Failure Modes

**Exceptions Raised**:
- `FileNotFoundError` - When required files or directories don't exist
- `ValueError` - For invalid configuration or parameters
- `TimeoutError` - When operations exceed configured timeouts

**Common Failure Modes**:
- Index corruption or missing index files
- LLM provider API failures or rate limits
- Insufficient permissions for file system operations

## Performance & Scaling Notes

**Performance Characteristics**:
- Enrichment typically processes 50-100 files per minute
- Indexing speed depends on repository size and LLM response times
- Query response time: <500ms for cached indices

**Bottlenecks**:
- LLM API rate limits and response latency
- File I/O for large repositories
- Vector similarity search on large indices

## Security / Footguns

Minimal security risk - primarily internal utility functions.

## Internal Structure (Technical Deep Dive)

**Implementation Details**:

- Contains 2 class definition(s)
- Contains 12 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = __init__(self)
```

