<!--
SOURCE_FILE: tools/rag/config.py
SOURCE_HASH: sha256:815f5ae8081a8ce3f56acc6e627b1f5d98d337fbeb907ec5ba669f246145c6e9
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/config.py – High-Level Overview

**tools/rag/config.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `_to_path(repo_root, value)`
  Function: _to_path

- `rag_dir(repo_root)`
  Return the repository-local directory that houses RAG artefacts.

- `_env_index_path(repo_root)`
  Function: _env_index_path

- `index_path_for_write(repo_root)`
  Resolve the index database path that should be written to.

- `index_path_for_read(repo_root)`
  Resolve the index database path to read from, falling back to v1 if needed.

- `spans_export_path(repo_root)`
  Return the JSONL export path, keyed by the active index version.

- `ensure_rag_storage(repo_root)`
  Create the `.rag` directory if it does not exist.

- `_env_flag(name, default)`
  Function: _env_flag

- `_preset_defaults()`
  Function: _preset_defaults

- `embedding_model_preset()`
  Function: embedding_model_preset


## Data & Schema

**Configuration Structure**: 
```
{
  key: str - Configuration parameter name
  value: Any - Configuration value
  description: str - Human-readable explanation
}
```


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `os`
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

- Contains 21 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = _to_path(repo_root, value)
```

