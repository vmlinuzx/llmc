<!--
SOURCE_FILE: tools/rag_daemon/state_store.py
SOURCE_HASH: sha256:df443cdf739cc4f031e627d1e569fea0ee8fc82ca04a269f6f0eaa87892e1f26
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag_daemon/state_store.py – High-Level Overview

**tools/rag_daemon/state_store.py** is a tool module providing RAG daemon services, repository integration, or specialized RAG functionality. It supports background processing and infrastructure operations.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `__init__(self, root)`
  Function: __init__

- `_path_for(self, repo_id)`
  Function: _path_for

- `load_all(self)`
  Function: load_all

- `get(self, repo_id)`
  Function: get

- `upsert(self, state)`
  Function: upsert

- `update(self, repo_id, mutator)`
  Function: update

- `_load_path(self, path)`
  Function: _load_path

- `_serialize(self, state)`
  Function: _serialize

- `_deserialize(self, data)`
  Function: _deserialize

- `encode_dt(dt)`
  Function: encode_dt

- **StateStore** (class)
  - Key methods: __init__, _path_for, load_all, get, upsert
  - Persist per-repo state as individual JSON files.


## Data & Schema

### StateStore

Persist per-repo state as individual JSON files.

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `dataclasses`
- `datetime`
- `json`
- `models`
- `pathlib`
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

- Contains 1 class definition(s)
- Contains 11 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = __init__(self, root)
```

