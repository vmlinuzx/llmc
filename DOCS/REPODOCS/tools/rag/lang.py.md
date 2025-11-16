<!--
SOURCE_FILE: tools/rag/lang.py
SOURCE_HASH: sha256:8a0ea2415cbc6d5ee6e34b336592484627862d02e66025413e0f23a45fc9f91a
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/lang.py – High-Level Overview

**tools/rag/lang.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `_language(name)`
  Function: _language

- `_parser(name)`
  Function: _parser

- `language_for_path(path)`
  Function: language_for_path

- `is_supported(path)`
  Function: is_supported

- `parse_source(lang, source)`
  Function: parse_source

- `_node_text(node, source)`
  Function: _node_text

- `_make_span(file_path, lang, symbol, kind, node, source, doc_hint)`
  Function: _make_span

- `_python_doc_hint(node, source)`
  Function: _python_doc_hint

- `_collect_python(node, source, file_path, scope)`
  Function: _collect_python

- `_collect_js(node, source, file_path, lang, scope)`
  Function: _collect_js


## Data & Schema


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `functools`
- `pathlib`
- `re`
- `tree_sitter`
- `tree_sitter_languages`
- `types`
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

- Contains 15 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = _language(name)
```

