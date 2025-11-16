<!--
SOURCE_FILE: tools/rag/cli.py
SOURCE_HASH: sha256:1038d9021b9057d694c1e7b546f7b90891f70fbce3e22b65079777e3c0e6a802
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/cli.py – High-Level Overview

**tools/rag/cli.py** is a command-line interface and execution engine for the RAG (Retrieval-Augmented Generation) system. It provides CLI commands, workflows, and orchestration logic for indexing, searching, and enriching code repositories.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `_db_path(repo_root)`
  Function: _db_path

- `_repo_paths(repo_root)`
  Function: _repo_paths

- `_spans_export_path(repo_root)`
  Function: _spans_export_path

- `_find_repo_root(start)`
  Function: _find_repo_root

- `cli()`
  RAG ingestion CLI

- `index(since, no_export)`
  Index the repository (full or incremental).

- `_collect_paths(paths, use_stdin)`
  Function: _collect_paths

- `sync(paths, since, use_stdin)`
  Incrementally update spans for selected files.

- `stats(as_json)`
  Print summary stats for the current index.

- `paths()`
  Show index storage paths.


## Data & Schema


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `analytics`
- `benchmark`
- `click`
- `config`
- `database`
- `diagnostics.health_check`
- `export_data`
- `indexer`
- `json`

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

- Contains 18 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = _db_path(repo_root)
```

