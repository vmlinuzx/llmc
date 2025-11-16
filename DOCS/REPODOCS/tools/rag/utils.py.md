<!--
SOURCE_FILE: tools/rag/utils.py
SOURCE_HASH: sha256:51a72a0405ea8707d8685f7f193005b135a51d9e3c4b211d30e760cbde126bee
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/utils.py – High-Level Overview

**tools/rag/utils.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `find_repo_root(start)`
  Function: find_repo_root

- `iter_source_files(repo_root, include_paths)`
  Function: iter_source_files

- `_iter_directory(repo_root, directory, matcher)`
  Function: _iter_directory

- `git_commit_sha(repo_root)`
  Function: git_commit_sha

- `git_changed_paths(repo_root, since)`
  Function: git_changed_paths

- `language_from_path(path)`
  Function: language_from_path

- `_load_additional_ignores(repo_root)`
  Load extra ignore globs from .ragignore and env (LLMC_RAG_EXCLUDE).

- `_gitignore_matcher(repo_root)`
  Function: _gitignore_matcher

- `_is_ignored(rel_path)`
  Function: _is_ignored

- `_matches_extra(rel_path)`
  Function: _matches_extra


## Data & Schema


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `fnmatch`
- `functools`
- `lang`
- `os`
- `pathlib`
- `subprocess`
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

- ⚠️ Shell execution with file paths - ensure paths are validated

## Internal Structure (Technical Deep Dive)

**Implementation Details**:

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
# result = find_repo_root(start)
```

