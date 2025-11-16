<!--
SOURCE_FILE: tools/rag/quality.py
SOURCE_HASH: sha256:80ba7f2870b40754e864bfd2d0303aae0bd4dd6f887b13ecbf1db00cb3655461
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/quality.py – High-Level Overview

**tools/rag/quality.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `run_quality_check(repo_path, verbose)`
  Run quality check on a repo's RAG database using canonical classifier.

- `format_quality_summary(result, repo_name)`
  Format quality check result for console output.


## Data & Schema


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern

## Dependencies & Integration Points

**Python Imports**:
- `argparse`
- `datetime`
- `pathlib`
- `sqlite3`
- `sys`
- `tools.rag.config`
- `tools.rag.quality_check`

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

- Contains 2 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = run_quality_check(repo_path, verbose)
```

