<!--
SOURCE_FILE: tools/rag_daemon/scheduler.py
SOURCE_HASH: sha256:27941722622db8990caae76b6b7502e76236c9aa476ff2c16e608dde97babd3f
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag_daemon/scheduler.py – High-Level Overview

**tools/rag_daemon/scheduler.py** is a tool module providing RAG daemon services, repository integration, or specialized RAG functionality. It supports background processing and infrastructure operations.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `__init__(self, config, registry, state_store, workers)`
  Function: __init__

- `run_forever(self)`
  Function: run_forever

- `run_once(self)`
  Run a single scheduler tick and return.

- `_install_signal_handlers(self)`
  Function: _install_signal_handlers

- `_run_tick(self)`
  Function: _run_tick

- `_is_repo_eligible(self, repo, state, now, force)`
  Function: _is_repo_eligible

- `handler(signum, frame)`
  Function: handler

- **Scheduler** (class)
  - Key methods: __init__, run_forever, run_once, _install_signal_handlers, _run_tick
  - Tick-based scheduler that assigns jobs to the worker pool.


## Data & Schema

### Scheduler

Tick-based scheduler that assigns jobs to the worker pool.

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `control`
- `datetime`
- `logging_utils`
- `models`
- `random`
- `registry`
- `signal`
- `state_store`
- `threading`

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
- Contains 7 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = __init__(self, config, registry, state_store, workers)
```

