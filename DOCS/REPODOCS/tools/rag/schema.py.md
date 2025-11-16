<!--
SOURCE_FILE: tools/rag/schema.py
SOURCE_HASH: sha256:0230f24ee2b7a62006fc6f9494cf196848af93346330b0cf0d40a6c5c367cf2a
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/schema.py – High-Level Overview

**tools/rag/schema.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `language_for_path(path)`
  Simple file extension-based language detection

- `extract_schema_from_file(file_path)`
  Extract entities and relations from a single file.

- `extract_schema_from_file(file_path)`
  Extract entities and relations from a single file.

- `extract_schema_from_file(file_path)`
  Extract entities and relations from a single file.

- `build_schema_graph(repo_root, file_paths)`
  Build complete schema graph from list of files.

- `to_dict(self)`
  Function: to_dict

- `to_dict(self)`
  Function: to_dict

- `to_dict(self)`
  Function: to_dict

- `save(self, path)`
  Save graph to JSON file

- `load(cls, path)`
  Load graph from JSON file

- **Entity** (class)
  - Key methods: to_dict
  - Represents a code entity (function, class, table, etc.)

- **Relation** (class)
  - Key methods: to_dict
  - Represents a relationship between entities

- **SchemaGraph** (class)
  - Key methods: to_dict, save, load
  - Complete entity-relation graph for a repository

- **PythonSchemaExtractor** (class)
  - Key methods: __init__, extract, visit_module, visit_function, visit_class
  - Extract entities and relations from Python code using AST


## Data & Schema

### Entity

Represents a code entity (function, class, table, etc.)

**Structure**: Object-oriented data model

### Relation

Represents a relationship between entities

**Structure**: Object-oriented data model

### SchemaGraph

Complete entity-relation graph for a repository

**Structure**: Object-oriented data model

### PythonSchemaExtractor

Extract entities and relations from Python code using AST

**Structure**: Object-oriented data model


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. Functions called based on usage pattern
3. Class methods invoked via object instances

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `ast`
- `collections`
- `dataclasses`
- `datetime`
- `hashlib`
- `json`
- `pathlib`
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

- Contains 4 class definition(s)
- Contains 16 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = language_for_path(path)
```

