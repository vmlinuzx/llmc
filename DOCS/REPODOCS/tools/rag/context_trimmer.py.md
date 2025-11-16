<!--
SOURCE_FILE: tools/rag/context_trimmer.py
SOURCE_HASH: sha256:005da7bca398b752970c91440516ffe1f67b22be6b0772427a7c47818575bcd1
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/context_trimmer.py – High-Level Overview

**tools/rag/context_trimmer.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `create_default_config(max_tokens)`
  Create a sensible default configuration.

- `search_with_trimming(query)`
  Search and trim results to fit within token budget.

- `available_for_chunks(self)`
  Calculate tokens available for retrieved chunks.

- `__init__(self, config)`
  Function: __init__

- `count_tokens(self, text)`
  Count tokens in text using tiktoken or fallback estimation.

- `trim_to_budget(self, chunks, query)`
  Trim chunks to fit within token budget.

- `_apply_mmr(self, chunks, query, top_k)`
  Apply Maximal Marginal Relevance for diversity.

- `_simple_similarity(self, text1, text2)`
  Simple Jaccard similarity for diversity calculation.

- `_enforce_budget(self, chunks)`
  Enforce token budget with greedy selection.

- **ChunkItem** (class)
  - A chunk candidate for context inclusion.

- **ContextBudget** (class)
  - Key methods: available_for_chunks
  - Token budget configuration for a context window.

- **TrimConfig** (class)
  - Configuration for context trimming strategy.

- **ContextTrimmer** (class)
  - Key methods: __init__, count_tokens, trim_to_budget, _apply_mmr, _simple_similarity
  - Manages intelligent context window trimming.


## Data & Schema

### ChunkItem

A chunk candidate for context inclusion.

**Structure**: Object-oriented data model

### ContextBudget

Token budget configuration for a context window.

**Structure**: Object-oriented data model

### TrimConfig

Configuration for context trimming strategy.

**Structure**: Object-oriented data model

### ContextTrimmer

Manages intelligent context window trimming.

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `dataclasses`
- `numpy`
- `pathlib`
- `search`
- `tiktoken`
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

- Contains 4 class definition(s)
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
# result = create_default_config(max_tokens)
```

