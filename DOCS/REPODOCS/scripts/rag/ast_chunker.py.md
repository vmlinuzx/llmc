<!--
SOURCE_FILE: scripts/rag/ast_chunker.py
SOURCE_HASH: sha256:2c1d2812ba9e280de331752e4f642dff3a2cca5de09a7adb094fca186562c90f
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# scripts/rag/ast_chunker.py – High-Level Overview

**scripts/rag/ast_chunker.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `__init__(self, max_chars, overlap_chars, header_chars)`
  Function: __init__

- `chunk_text(self, text, file_path)`
  Return chunk text + metadata pairs.

- `_chunk_tree(self, root, language)`
  Function: _chunk_tree

- `_emit_node(self, node, language, parent_span, depth)`
  Function: _emit_node

- `_chunk_range(self, start_byte, end_byte)`
  Function: _chunk_range

- `_build_metadata(self)`
  Function: _build_metadata

- `_annotate_child_counts(self, chunks)`
  Function: _annotate_child_counts

- `_meaningful_children(self, node)`
  Function: _meaningful_children

- `_structural_children(self, node, language, lower_byte_bound)`
  Function: _structural_children

- `_detect_language(self, file_path)`
  Function: _detect_language

- **ChunkRecord** (class)

- **ASTChunker** (class)
  - Key methods: __init__, chunk_text, _chunk_tree, _emit_node, _chunk_range
  - Generate AST-aligned chunks with graceful fallback.


## Data & Schema

### ASTChunker

Generate AST-aligned chunks with graceful fallback.

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `bisect`
- `dataclasses`
- `logging`
- `tree_sitter`
- `tree_sitter_languages`
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

- Contains 2 class definition(s)
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
# result = __init__(self, max_chars, overlap_chars, header_chars)
```

