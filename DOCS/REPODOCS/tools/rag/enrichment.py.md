<!--
SOURCE_FILE: tools/rag/enrichment.py
SOURCE_HASH: sha256:35eef7025d4294e40455eefa84f533720c0a50ee26cc527452234bbac106d576
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/rag/enrichment.py – High-Level Overview

**tools/rag/enrichment.py** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `__post_init__(self)`
  Function: __post_init__

- `__init__(self, graph_store)`
  Function: __init__

- `analyze(self, query)`
  Analyze query to extract enrichment features.

- `_detect_entities(self, query)`
  Extract potential entity identifiers from query.

- `_estimate_complexity(self, query, features)`
  Estimate query complexity on scale 0-10.

- `__init__(self, graph_store, analyzer)`
  Function: __init__

- `retrieve(self, query, vector_results, max_graph_results, max_hops)`
  Hybrid retrieval: merge vector results with graph-based results.

- `_neighbors_to_spans(self, neighbors)`
  Convert graph neighbors to SpanRecords

- `_merge_results(self, vector_results, graph_results)`
  Merge and deduplicate vector + graph results.

- **EnrichmentFeatures** (class)
  - Key methods: __post_init__
  - Features extracted from query for router decision-making

- **QueryAnalyzer** (class)
  - Key methods: __init__, analyze, _detect_entities, _estimate_complexity
  - Analyzes queries to detect entities and relationships

- **HybridRetriever** (class)
  - Key methods: __init__, retrieve, _neighbors_to_spans, _merge_results
  - Combines vector search with graph traversal for hybrid retrieval.


## Data & Schema

### EnrichmentFeatures

Features extracted from query for router decision-making

**Structure**: Object-oriented data model

### QueryAnalyzer

Analyzes queries to detect entities and relationships

**Structure**: Object-oriented data model

### HybridRetriever

Combines vector search with graph traversal for hybrid retrieval.

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
- `graph`
- `pathlib`
- `re`
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

- Contains 3 class definition(s)
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
# result = __post_init__(self)
```

