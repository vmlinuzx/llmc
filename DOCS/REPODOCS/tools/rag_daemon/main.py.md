<!--
SOURCE_FILE: tools/rag_daemon/main.py
SOURCE_HASH: sha256:ffbf10d045a0a5941d11db09d919c45d5c5851c2d55eba1738dc11473c4a2315
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag_daemon/main.py – High-Level Overview

**tools/rag_daemon/main.py** is a tool module providing RAG daemon services, repository integration, or specialized RAG functionality. It supports background processing and infrastructure operations.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `_print_top_level_help()`
  Print a tree-style help overview for llmc-rag-daemon.

- `_build_parser()`
  Function: _build_parser

- `_make_scheduler(config)`
  Function: _make_scheduler

- `_cmd_run(config)`
  Function: _cmd_run

- `_cmd_tick(config)`
  Function: _cmd_tick

- `_cmd_config(config, json_output)`
  Function: _cmd_config

- `_cmd_doctor(config)`
  Basic health checks for daemon environment.

- `main(argv)`
  Function: main


## Data & Schema


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. `main()` called

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `argparse`
- `config`
- `dataclasses`
- `json`
- `logging_utils`
- `models`
- `os`
- `pathlib`
- `registry`

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
# result = _print_top_level_help()
```

