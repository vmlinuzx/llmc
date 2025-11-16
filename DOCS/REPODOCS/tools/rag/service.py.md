<!--
SOURCE_FILE: tools/rag/service.py
SOURCE_HASH: sha256:5fae85a141f662f6699f7a8ab0547466036f22b32a07de8117a861cc78c498ef
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/service.py – High-Level Overview

**tools/rag/service.py** is a command-line interface and execution engine for the RAG (Retrieval-Augmented Generation) system. It provides CLI commands, workflows, and orchestration logic for indexing, searching, and enriching code repositories.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `cmd_start(args, state, tracker)`
  Start the service.

- `cmd_stop(args, state, tracker)`
  Stop the service.

- `cmd_status(args, state, tracker)`
  Show service status.

- `cmd_register(args, state, tracker)`
  Register a repo - register + /full/path 

- `cmd_unregister(args, state, tracker)`
  Unregister a repo - unregister + /full/path

- `cmd_clear_failures(args, state, tracker)`
  Clear failure cache.

- `main(argv)`
  Function: main

- `__init__(self)`
  Function: __init__

- `_load(self)`
  Function: _load

- `save(self)`
  Function: save

- **ServiceState** (class)
  - Key methods: __init__, _load, save, add_repo, remove_repo
  - Manage service state persistence.

- **FailureTracker** (class)
  - Key methods: __init__, _init_db, record_failure, record_repo_failure, is_failed
  - Track and manage enrichment failures.

- **RAGService** (class)
  - Key methods: __init__, handle_signal, _load_logging_cfg, _load_full_toml, run_rag_cli
  - Main RAG service orchestrator.


## Data & Schema

### ServiceState

Manage service state persistence.

**Structure**: Object-oriented data model

### FailureTracker

Track and manage enrichment failures.

**Structure**: Object-oriented data model

### RAGService

Main RAG service orchestrator.

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. `main()` called
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `argparse`
- `datetime`
- `json`
- `os`
- `pathlib`
- `scripts.llmc_log_manager`
- `signal`
- `sqlite3`
- `subprocess`
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

- ⚠️ Shell execution with file paths - ensure paths are validated

## Internal Structure (Technical Deep Dive)

**Implementation Details**:

- Contains 3 class definition(s)
- Contains 32 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = cmd_start(args, state, tracker)
```

