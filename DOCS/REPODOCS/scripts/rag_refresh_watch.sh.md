<!--
SOURCE_FILE: scripts/rag_refresh_watch.sh
SOURCE_HASH: sha256:3c68773b9f64408f25a0fee64e557aea5656b014ffd9616436c5217d2ac905c1
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# scripts/rag_refresh_watch.sh – High-Level Overview

**scripts/rag_refresh_watch.sh** is a RAG-related script that automates indexing, enrichment, or query workflows. It performs batch processing and orchestrates RAG operations.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `die()`
  Function: die

- `ensure_tmux()`
  Function: ensure_tmux

- `session_exists()`
  Function: session_exists

- `start_session()`
  Function: start_session

- `stop_session()`
  Function: stop_session

- `show_status()`
  Function: show_status

- `toggle_session()`
  Function: toggle_session

- `usage()`
  Function: usage

- `die` - Shell function
- `ensure_tmux` - Shell function
- `session_exists` - Shell function
- `start_session` - Shell function
- `stop_session` - Shell function

## Data & Schema


## Control Flow & Lifecycle

Typical execution flow:
1. Script invoked via shell command
2. Interpreter: `#!/usr/bin/env bash`
3. Shell function(s) executed: die, ensure_tmux, session_exists

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

- Contains 8 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```bash
# #!/usr/bin/env bash
# scripts/rag_refresh_watch.sh

# ./scripts/rag_refresh_watch.sh die
```

