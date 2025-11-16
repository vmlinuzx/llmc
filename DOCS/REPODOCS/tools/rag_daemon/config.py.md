<!--
SOURCE_FILE: tools/rag_daemon/config.py
SOURCE_HASH: sha256:9cf5711b06c9377ee25cb3991d720ead068a10bb5471f27d8047ab0884a63172
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag_daemon/config.py – High-Level Overview

**tools/rag_daemon/config.py** is a tool module providing RAG daemon services, repository integration, or specialized RAG functionality. It supports background processing and infrastructure operations.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `_expand(path)`
  Function: _expand

- `load_config(path)`
  Load daemon config from YAML.

- `get_int(key, default)`
  Function: get_int

- `get_str(key, default)`
  Function: get_str


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
- `models`
- `os`
- `pathlib`
- `typing`
- `yaml`

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

- Contains 4 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = _expand(path)
```

