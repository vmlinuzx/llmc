<!--
SOURCE_FILE: scripts/rag/index_workspace.py
SOURCE_HASH: sha256:a8c7ac777237948e596adeace648dcba213fb5f4d9e0895ec50e7c18b7e1b15b
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# scripts/rag/index_workspace.py – High-Level Overview

**scripts/rag/index_workspace.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `resolve_rag_db_path()`
  Resolve RAG database path with fallback logic.

- `main()`
  Function: main

- `__init__(self, workspace_root, db_path)`
  Function: __init__

- `should_index_file(self, file_path)`
  Check if file should be indexed

- `get_project_name(self, file_path)`
  Extract project name from file path

- `get_git_info(self, file_path)`
  Get git info for file if available

- `chunk_text(self, text, file_path)`
  Delegate to AST-aware chunker with fallback.

- `file_hash(self, file_path)`
  Generate hash of file content

- `index_file(self, file_path)`
  Index a single file, return number of chunks added

- `index_workspace(self, project_filter, reindex)`
  Index entire workspace or specific project

- **WorkspaceIndexer** (class)
  - Key methods: __init__, should_index_file, get_project_name, get_git_info, chunk_text


## Data & Schema

### WorkspaceIndexer

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. `main()` called
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `argparse`
- `ast_chunker`
- `chromadb`
- `chromadb.config`
- `datetime`
- `git`
- `hashlib`
- `os`
- `pathlib`
- `sentence_transformers`

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
# result = resolve_rag_db_path()
```

