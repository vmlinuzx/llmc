<!--
SOURCE_FILE: tools/claude_minimax_rag_wrapper.sh
SOURCE_HASH: sha256:66f50ebc67bd6150ee90c8f0ba42d0f6160746a5701add6401e6f0d2ff0d5b87
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/claude_minimax_rag_wrapper.sh – High-Level Overview

**tools/claude_minimax_rag_wrapper.sh** is a tool module providing RAG daemon services, repository integration, or specialized RAG functionality. It supports background processing and infrastructure operations.

## Responsibilities & Behavior (for Humans)

- Processes code repositories for semantic search and retrieval
- Indexes files and generates embeddings for semantic understanding
- Enriches code with contextual metadata and summaries

## Public Surface Area (API Snapshot)

- `err()`
  Function: err

- `have_cmd()`
  Function: have_cmd

- `detect_repo_root()`
  Function: detect_repo_root

- `read_top()`
  Function: read_top

- `repo_snapshot()`
  Function: repo_snapshot

- `build_preamble()`
  Function: build_preamble

- `configure_minimax_env()`
  Function: configure_minimax_env

- `main()`
  Function: main

- `err` - Shell function
- `have_cmd` - Shell function
- `detect_repo_root` - Shell function
- `read_top` - Shell function
- `repo_snapshot` - Shell function

## Data & Schema


## Control Flow & Lifecycle

Typical execution flow:
1. Script invoked via shell command
2. Interpreter: `#!/usr/bin/env bash`
3. Shell function(s) executed: err, have_cmd, detect_repo_root

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
# tools/claude_minimax_rag_wrapper.sh

# ./scripts/claude_minimax_rag_wrapper.sh err
```

