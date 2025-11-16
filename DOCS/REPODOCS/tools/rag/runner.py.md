<!--
SOURCE_FILE: tools/rag/runner.py
SOURCE_HASH: sha256:5f3f1be975ce61515ee0062bc97f49f8c59c1e9ff97247172c79d3d496667e4f
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/runner.py – High-Level Overview

**tools/rag/runner.py** is a command-line interface and execution engine for the RAG (Retrieval-Augmented Generation) system. It provides CLI commands, workflows, and orchestration logic for indexing, searching, and enriching code repositories.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `log(msg)`
  Function: log

- `env_bool(name, default)`
  Function: env_bool

- `env_int(name, default)`
  Function: env_int

- `sha256_file(path)`
  Function: sha256_file

- `load_cached_hashes(index_path)`
  Function: load_cached_hashes

- `_extra_patterns(repo_root)`
  Function: _extra_patterns

- `_matches_extra(path, patterns)`
  Function: _matches_extra

- `fnmatch(path, pattern)`
  Function: fnmatch

- `iter_repo_files(repo_root)`
  Function: iter_repo_files

- `current_hashes(repo_root, extra_patterns)`
  Function: current_hashes


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
- `fnmatch`
- `hashlib`
- `json`
- `lang`
- `os`
- `pathlib`
- `sqlite3`

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

- Contains 22 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = log(msg)
```

