<!--
SOURCE_FILE: tools/rag_repo/registry.py
SOURCE_HASH: sha256:487b419a50760e32901605780be1976d9aa448dedab4046fb76956a69711e55c
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag_repo/registry.py – High-Level Overview

**tools/rag_repo/registry.py** is a tool module providing RAG daemon services, repository integration, or specialized RAG functionality. It supports background processing and infrastructure operations.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `__init__(self, config)`
  Function: __init__

- `load_all(self)`
  Function: load_all

- `save_all(self, entries)`
  Function: save_all

- `register(self, entry)`
  Function: register

- `unregister_by_id(self, repo_id)`
  Function: unregister_by_id

- `list_entries(self)`
  Function: list_entries

- `find_by_path(self, repo_path)`
  Function: find_by_path

- `find_by_id(self, repo_id)`
  Function: find_by_id

- **RegistryAdapter** (class)
  - Key methods: __init__, load_all, save_all, register, unregister_by_id
  - YAML-based registry of repos for LLMC RAG.


## Data & Schema

### RegistryAdapter

YAML-based registry of repos for LLMC RAG.

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
- `models`
- `os`
- `pathlib`
- `typing`
- `utils`
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

- Contains 1 class definition(s)
- Contains 8 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = __init__(self, config)
```

