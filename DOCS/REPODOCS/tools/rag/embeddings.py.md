<!--
SOURCE_FILE: tools/rag/embeddings.py
SOURCE_HASH: sha256:767a9f812bbf253ab5907c098bf9c663d2ba2c31dc0cf325f883726cd3cfa295
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/embeddings.py – High-Level Overview

**tools/rag/embeddings.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `_load_sentence_transformer(model_name, device)`
  Function: _load_sentence_transformer

- `_select_device()`
  Function: _select_device

- `_deterministic_embedding(payload, dim)`
  Hash-based embedding placeholder to keep the worker deterministic/offline.

- `build_embedding_backend(model_name)`
  Function: build_embedding_backend

- `_loader(name, dev)`
  Function: _loader

- `device_label()`
  Function: device_label

- `__init__(self, spec)`
  Function: __init__

- `model_name(self)`
  Function: model_name

- `dim(self)`
  Function: dim

- `embed_passages(self, texts)`
  Function: embed_passages

- **EmbeddingSpec** (class)

- **EmbeddingBackend** (class)
  - Key methods: __init__, model_name, dim, embed_passages, embed_queries

- **HashEmbeddingBackend** (class)
  - Key methods: __init__, _encode, embed_passages, embed_queries

- **SentenceTransformerBackend** (class)
  - Key methods: __init__, _encode, embed_passages, embed_queries


## Data & Schema

### EmbeddingBackend

**Structure**: Object-oriented data model

### HashEmbeddingBackend

**Structure**: Object-oriented data model

### SentenceTransformerBackend

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `config`
- `dataclasses`
- `functools`
- `hashlib`
- `logging`
- `sentence_transformers`
- `struct`
- `time`
- `torch`

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
- Contains 21 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = _load_sentence_transformer(model_name, device)
```

