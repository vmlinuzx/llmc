<!--
SOURCE_FILE: tools/rag/indexer.py
SOURCE_HASH: sha256:25b59bcebb779629eb69006aa8dbd31940655e1bb34af7602c3afe9020143124
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/indexer.py – High-Level Overview

**tools/rag/indexer.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `repo_paths(repo_root)`
  Function: repo_paths

- `db_path(repo_root)`
  Function: db_path

- `spans_export_path(repo_root)`
  Function: spans_export_path

- `ensure_storage(repo_root)`
  Function: ensure_storage

- `compute_hash(data)`
  Function: compute_hash

- `populate_span_hashes(spans, source, lang)`
  Function: populate_span_hashes

- `build_file_record(file_path, lang, repo_root, source)`
  Function: build_file_record

- `generate_sidecar_if_enabled(file_path, lang, source, repo_root)`
  Generate .md sidecar file if enabled via environment variable.

- `index_repo(include_paths, since, export_json)`
  Function: index_repo

- `sync_paths(paths)`
  Function: sync_paths

- **IndexStats** (class)
  - Key methods: files, spans, sidecars, unchanged


## Data & Schema

### IndexStats

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `config`
- `database`
- `hashlib`
- `json`
- `lang`
- `os`
- `pathlib`
- `sidecar_generator`
- `sys`

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
- Contains 14 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = repo_paths(repo_root)
```

