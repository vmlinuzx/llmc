<!--
SOURCE_FILE: tools/codex_rag_wrapper.sh
SOURCE_HASH: sha256:5d987f4ea10219b60fd6b60199390e4a7151c8f1b8fc28e0cc8268f542c9a034
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/codex_rag_wrapper.sh – High-Level Overview

**tools/codex_rag_wrapper.sh** is a tool module providing RAG daemon services, repository integration, or specialized RAG functionality. It supports background processing and infrastructure operations.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `resolve_approval_policy()`
  Function: resolve_approval_policy

- `section_from()`
  Function: section_from

- `build_preamble()`
  Function: build_preamble

- `resolve_approval_policy` - Shell function
- `section_from` - Shell function
- `build_preamble` - Shell function

## Data & Schema


## Control Flow & Lifecycle

Typical execution flow:
1. Script invoked via shell command
3. Shell function(s) executed: resolve_approval_policy, section_from, build_preamble

## Dependencies & Integration Points

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

- ⚠️ Shell execution with file paths - ensure paths are validated

## Internal Structure (Technical Deep Dive)

**Implementation Details**:

- Contains 3 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```bash
# tools/codex_rag_wrapper.sh

# ./scripts/codex_rag_wrapper.sh resolve_approval_policy
```

