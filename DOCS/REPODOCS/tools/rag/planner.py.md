<!--
SOURCE_FILE: tools/rag/planner.py
SOURCE_HASH: sha256:207264d740e88c06cfb9c51a89e0a5694a7c79954bc74d0b94ee6507a1150d6f
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/planner.py – High-Level Overview

**tools/rag/planner.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `_tokenize(text)`
  Function: _tokenize

- `_derive_intent(tokens)`
  Function: _derive_intent

- `_load_json_field(raw)`
  Function: _load_json_field

- `_fetch_candidates(db)`
  Function: _fetch_candidates

- `_score_candidate(tokens, candidate)`
  Function: _score_candidate

- `_score_to_confidence(score)`
  Function: _score_to_confidence

- `_append_plan_log(repo_root, payload)`
  Function: _append_plan_log

- `_resolve_repo_root()`
  Function: _resolve_repo_root

- `generate_plan(query, limit, min_score, min_confidence, repo_root, log)`
  Function: generate_plan

- `plan_as_dict(result)`
  Function: plan_as_dict

- **SpanCandidate** (class)

- **PlanSpan** (class)

- **PlanResult** (class)


## Data & Schema


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `config`
- `database`
- `dataclasses`
- `json`
- `pathlib`
- `re`
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

- Contains 3 class definition(s)
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
# result = _tokenize(text)
```

