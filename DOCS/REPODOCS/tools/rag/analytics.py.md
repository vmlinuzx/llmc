<!--
SOURCE_FILE: tools/rag/analytics.py
SOURCE_HASH: sha256:84338f89f60ba4afb0eacde413796537d76622a207069d9a750161ab5ef79309
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/analytics.py – High-Level Overview

**tools/rag/analytics.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `format_analytics(summary)`
  Format analytics summary as human-readable string.

- `run_analytics(repo_root, days)`
  Run analytics and print report.

- `__init__(self, db_path)`
  Function: __init__

- `_initialize_db(self)`
  Initialize analytics database.

- `log_query(self, query_text, results_count, files_retrieved)`
  Log a search query.

- `get_analytics(self, days)`
  Get analytics summary for the last N days.

- `get_recent_queries(self, limit)`
  Get recent queries.

- **QueryRecord** (class)
  - A recorded search query.

- **AnalyticsSummary** (class)
  - Summary of analytics over a time period.

- **QueryTracker** (class)
  - Key methods: __init__, _initialize_db, log_query, get_analytics, get_recent_queries
  - Tracks and analyzes search queries.


## Data & Schema

### QueryRecord

A recorded search query.

**Structure**: Object-oriented data model

### AnalyticsSummary

Summary of analytics over a time period.

**Structure**: Object-oriented data model

### QueryTracker

Tracks and analyzes search queries.

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `argparse`
- `dataclasses`
- `datetime`
- `json`
- `pathlib`
- `sqlite3`
- `typing`
- `utils`

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

- Contains 3 class definition(s)
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
# result = format_analytics(summary)
```

