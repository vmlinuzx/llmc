<!--
SOURCE_FILE: scripts/rag_quality_check.py
SOURCE_HASH: sha256:b99de8990825d405371f8ac919a42ea4f20e64b16cb0e0d6997de2ae001f6241
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# scripts/rag_quality_check.py – High-Level Overview

**scripts/rag_quality_check.py** is a RAG-related script that automates indexing, enrichment, or query workflows. It performs batch processing and orchestrates RAG operations.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `print_report(report, verbose)`
  Print human-readable report.

- `main()`
  Function: main

- `__init__(self, db_path)`
  Function: __init__

- `close(self)`
  Function: close

- `get_enrichment_stats(self)`
  Get basic statistics.

- `check_all_issues(self)`
  Check for all quality issues using canonical classifier.

- `delete_placeholder_data(self)`
  Delete all identified placeholder/fake data.

- `generate_report(self)`
  Generate comprehensive quality report.

- **QualityChecker** (class)
  - Key methods: __init__, close, get_enrichment_stats, check_all_issues, delete_placeholder_data
  - Check RAG enrichment data quality using canonical classifier.


## Data & Schema

### QualityChecker

Check RAG enrichment data quality using canonical classifier.

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
- `pathlib`
- `sqlite3`
- `sys`
- `tools.rag.config`
- `tools.rag.quality_check`
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

Minimal security risk - primarily internal utility functions.

## Internal Structure (Technical Deep Dive)

**Implementation Details**:

- Contains 1 class definition(s)
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
# result = print_report(report, verbose)
```

