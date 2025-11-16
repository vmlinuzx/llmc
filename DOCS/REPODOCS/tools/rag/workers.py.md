<!--
SOURCE_FILE: tools/rag/workers.py
SOURCE_HASH: sha256:28d693e9dc3a8945e33daf480bdf6b2d60a4e7b724e29b2034abac7cd0ca7cea
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/workers.py – High-Level Overview

**tools/rag/workers.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `_snippet(text, limit)`
  Function: _snippet

- `enrichment_plan(db, repo_root, limit, cooldown_seconds)`
  Build an enrichment plan, skipping spans touched within the cooldown window.

- `embedding_plan(db, repo_root, limit, model, dim)`
  Function: embedding_plan

- `_format_embedding_text(item, code)`
  Function: _format_embedding_text

- `execute_embeddings(db, repo_root, limit, model, dim)`
  Function: execute_embeddings

- `default_enrichment_callable(model)`
  Function: default_enrichment_callable

- `execute_enrichment(db, repo_root, llm_call, limit, model, cooldown_seconds)`
  Run enrichment over pending spans.

- `_within_range(lines, start, end)`
  Function: _within_range

- `validate_enrichment(payload, span_start, span_end)`
  Function: validate_enrichment

- `_call(prompt)`
  Function: _call


## Data & Schema


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `config`
- `database`
- `embeddings`
- `jsonschema`
- `pathlib`
- `sys`
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

- Contains 10 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = _snippet(text, limit)
```

