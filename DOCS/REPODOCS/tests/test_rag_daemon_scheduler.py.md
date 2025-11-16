<!--
SOURCE_FILE: tests/test_rag_daemon_scheduler.py
SOURCE_HASH: sha256:65b302b0b620016a0bd480356fc1518f80f1ba2a50e429f8c3c5b9d892e54c42
GENERATED_AT_UTC: 2025-11-16T00:49:27Z
-->

# tests/test_rag_daemon_scheduler.py – High-Level Overview

**tests/test_rag_daemon_scheduler.py** is a core component of the LLMC/RAG system providing make_config, test_scheduler_eligibility_basics, __init__.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `make_config(tmp_path)`
  Function: make_config

- `test_scheduler_eligibility_basics(tmp_path)`
  Function: test_scheduler_eligibility_basics

- `__init__(self, entries, path)`
  Function: __init__

- `load(self)`
  Function: load

- `__init__(self, config, state_store)`
  Function: __init__

- `submit_jobs(self, jobs)`
  Function: submit_jobs

- **DummyRegistry** (class)
  - Key methods: __init__, load

- **DummyWorkers** (class)
  - Key methods: __init__, submit_jobs


## Data & Schema

### DummyRegistry

**Structure**: Object-oriented data model

### DummyWorkers

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `DaemonConfig`
- `Path`
- `RegistryClient`
- `RepoDescriptor`
- `RepoState`
- `Scheduler`
- `StateStore`
- `WorkerPool`
- `datetime`
- `pathlib`

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

- Contains 2 class definition(s)
- Contains 6 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = make_config(tmp_path)
```

