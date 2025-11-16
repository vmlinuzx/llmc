<!--
SOURCE_FILE: tools/rag/database.py
SOURCE_HASH: sha256:a8e7727167773510689723f838a1d3354a3acdba81c9fb73b4c8874b00ec8621
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/database.py – High-Level Overview

**tools/rag/database.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `__init__(self, path)`
  Function: __init__

- `conn(self)`
  Function: conn

- `_run_migrations(self)`
  Function: _run_migrations

- `close(self)`
  Function: close

- `upsert_file(self, record)`
  Function: upsert_file

- `replace_spans(self, file_id, spans)`
  Replace spans for a file, preserving unchanged spans and their enrichments.

- `get_file_hash(self, path)`
  Get the stored file hash for a given path.

- `delete_file(self, path)`
  Function: delete_file

- `remove_missing_spans(self, valid_span_hashes)`
  Function: remove_missing_spans

- `stats(self)`
  Function: stats

- **Database** (class)
  - Key methods: __init__, conn, _run_migrations, close, upsert_file


## Data & Schema

### Database

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `contextlib`
- `json`
- `pathlib`
- `sqlite3`
- `struct`
- `sys`
- `time`
- `types`
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
- Contains 17 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = __init__(self, path)
```

