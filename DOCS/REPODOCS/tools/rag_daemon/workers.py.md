<!--
SOURCE_FILE: tools/rag_daemon/workers.py
SOURCE_HASH: sha256:186142a3bc013c0cd5716e429d0dcc163ae98d32c3e3366e4b0aafe97aa5937b
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag_daemon/workers.py – High-Level Overview

**tools/rag_daemon/workers.py** is a tool module providing RAG daemon services, repository integration, or specialized RAG functionality. It supports background processing and infrastructure operations.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `make_job_id()`
  Function: make_job_id

- `__init__(self, config, state_store)`
  Function: __init__

- `running_repo_ids(self)`
  Function: running_repo_ids

- `submit_jobs(self, jobs)`
  Function: submit_jobs

- `_run_job(self, job)`
  Function: _run_job

- `_invoke_runner(self, repo)`
  Function: _invoke_runner

- `_update_state_from_result(self, repo, result)`
  Function: _update_state_from_result

- `mark_running(state)`
  Function: mark_running

- `mutate(state)`
  Function: mutate

- **WorkerPool** (class)
  - Key methods: __init__, running_repo_ids, submit_jobs, _run_job, _invoke_runner
  - Fixed-size pool that executes RAG jobs for repos.


## Data & Schema

### WorkerPool

Fixed-size pool that executes RAG jobs for repos.

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `concurrent.futures`
- `datetime`
- `logging_utils`
- `models`
- `state_store`
- `subprocess`
- `threading`
- `typing`
- `uuid`

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

- Contains 1 class definition(s)
- Contains 9 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = make_job_id()
```

