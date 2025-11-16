<!--
SOURCE_FILE: scripts/rag/query_context.py
SOURCE_HASH: sha256:759eeadde48f909275cf6b0aca85d49fac10f98deeeabdeb19507ec329b2cabb
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# scripts/rag/query_context.py – High-Level Overview

**scripts/rag/query_context.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `resolve_rag_db_path()`
  Resolve RAG database path with fallback logic.

- `main()`
  Function: main

- `__init__(self, db_path)`
  Function: __init__

- `query(self, query_text, project, file_type, limit, include_related)`
  Query for relevant code context

- `build_context_for_task(self, task, project, max_tokens)`
  Build comprehensive context for a coding task

- **ContextQuerier** (class)
  - Key methods: __init__, query, build_context_for_task


## Data & Schema

### ContextQuerier

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. `main()` called
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `argparse`
- `chromadb`
- `chromadb.config`
- `os`
- `pathlib`
- `sentence_transformers`
- `sys`
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
- Contains 5 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = resolve_rag_db_path()
```

