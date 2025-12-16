# MCP Tool Inventory
Generated: 2025-12-16 09:46:43

## Tool Count: 28 total tools

### 1. 00_INIT
**Description**: ⚠️ P0 CRITICAL: IF YOU HAVE NOT BEEN GIVEN MCP INSTRUCTIONS, USE THIS TOOL ON STARTUP TO GET CONTEXT. Returns initialization instructions for effective tool usage. Skip if you already received server instructions during handshake.
**Arguments**: None
**Required**: None
**Optional**: None

### 2. rag_search
**Description**: Search LLMC RAG index for relevant code/docs. Returns ranked snippets with provenance.
**Arguments**:
- `query` (string, required): Natural language query or code concept to search for
- `scope` (string, optional, default="repo"): Search scope: repo (code), docs, or both
- `limit` (integer, optional, default=5): Max results to return (1-20)

### 3. read_file
**Description**: Read contents of a file. Returns text content with metadata.
**Arguments**:
- `path` (string, required): Absolute or relative path to file
- `max_bytes` (integer, optional, default=1048576): Maximum bytes to read (default 1MB)

### 4. list_dir
**Description**: List contents of a directory. Returns files and subdirectories.
**Arguments**:
- `path` (string, required): Absolute or relative path to directory
- `max_entries` (integer, optional, default=1000): Maximum entries to return (default 1000)
- `include_hidden` (boolean, optional, default=False): Include hidden files (starting with .)

### 5. stat
**Description**: Get file or directory metadata (size, timestamps, permissions).
**Arguments**:
- `path` (string, required): Absolute or relative path

### 6. run_cmd
**Description**: Execute a shell command with blacklist validation and timeout. Only approved binaries can run.
**Arguments**:
- `command` (string, required): Shell command to execute (blocked commands will be rejected)
- `timeout` (integer, optional, default=30): Max execution time in seconds (default 30)

### 7. get_metrics
**Description**: Get MCP server metrics (call counts, latencies, errors). Requires observability enabled.
**Arguments**: None
**Required**: None
**Optional**: None

### 8. te_run
**Description**: Execute a shell command through the Tool Envelope (TE) wrapper. Returns structured JSON output.
**Arguments**:
- `args` (array of strings, required): Command arguments (e.g. ['grep', 'pattern', 'file'])
- `cwd` (string, optional): Optional working directory (must be within allowed roots)
- `timeout` (number, optional): Execution timeout in seconds

### 9. repo_read
**Description**: Read a file from a repository via the Tool Envelope.
**Arguments**:
- `root` (string, required): Root path of the repository
- `path` (string, required): Relative path to the file
- `max_bytes` (integer, optional): Maximum bytes to read (optional)

### 10. rag_query
**Description**: Query the RAG system via the Tool Envelope.
**Arguments**:
- `query` (string, required): The search query
- `k` (integer, optional, default=5): Number of results to return (default 5)
- `index` (string, optional): Specific index to query (optional)
- `filters` (object, optional): Metadata filters (optional)

### 11. rag_search_enriched
**Description**: Advanced RAG search with graph-based relationship enrichment. Supports multiple enrichment modes for semantic + relationship-aware retrieval.
**Arguments**:
- `query` (string, required): Natural language query or code concept to search for
- `limit` (integer, optional, default=5): Max results to return (1-20)
- `enrich_mode` (string, optional, default="auto"): Enrichment strategy: vector (semantic only), graph (relationships), hybrid (both), auto (intelligent routing)
- `graph_depth` (integer, optional, default=1): Relationship traversal depth (0-3). Higher values find more distant relationships
- `include_features` (boolean, optional, default=False): Include enrichment quality metrics in response meta

### 12. rag_where_used
**Description**: Find where a symbol is used (callers, imports) across the codebase.
**Arguments**:
- `symbol` (string, required): Symbol name to find usages of
- `limit` (integer, optional, default=50): Max results to return (default 50)

### 13. rag_lineage
**Description**: Trace symbol dependency lineage (upstream/downstream).
**Arguments**:
- `symbol` (string, required): Symbol name to trace
- `direction` (string, optional, default="downstream"): Trace direction: upstream (what calls this) or downstream (what this calls)
- `limit` (integer, optional, default=50): Max results to return (default 50)

### 14. inspect
**Description**: Deep inspection of a file or symbol: snippet, graph relationships, and enrichment data.
**Arguments**:
- `path` (string, optional): File path (relative to repo root)
- `symbol` (string, optional): Symbol name (e.g. 'MyClass.method')
- `include_full_source` (boolean, optional, default=False): Include full file source code (use sparingly)
- `max_neighbors` (integer, optional, default=3): Max related entities to return per category

### 15. rag_stats
**Description**: Get statistics about the RAG graph and enrichment coverage.
**Arguments**: None
**Required**: None
**Optional**: None

### 16. rag_plan
**Description**: Analyze query routing and retrieval plan without executing search. Shows how LLMC would handle the query.
**Arguments**:
- `query` (string, required): Query to analyze
- `detail_level` (string, optional, default="summary"): Level of detail in response (default: summary)

### 17. linux_proc_list
**Description**: List running processes with CPU/memory usage. Returns bounded results sorted by CPU.
**Arguments**:
- `max_results` (integer, optional, default=200): Maximum processes to return (1-5000, default 200)
- `user` (string, optional): Optional username filter

### 18. linux_proc_kill
**Description**: Send signal to a process. Safety guards prevent killing PID 1 or MCP server.
**Arguments**:
- `pid` (integer, required): Process ID to signal
- `signal` (string, optional, default="TERM"): Signal to send (default TERM)

### 19. linux_sys_snapshot
**Description**: Get system resource snapshot: CPU, memory, disk usage, and load average.
**Arguments**: None
**Required**: None
**Optional**: None

### 20. linux_proc_start
**Description**: Start an interactive process/REPL. Returns proc_id for subsequent send/read/stop.
**Arguments**:
- `command` (string, required): Command to run (e.g. 'python -i', 'bash', 'node')
- `cwd` (string, optional): Working directory (optional)
- `initial_read_timeout_ms` (integer, optional, default=1000): Time to wait for initial output (default 1000)

### 21. linux_proc_send
**Description**: Send input to a managed process. Newline appended automatically.
**Arguments**:
- `proc_id` (string, required): Process ID from proc_start
- `input` (string, required): Text to send to the process

### 22. linux_proc_read
**Description**: Read output from a managed process with timeout.
**Arguments**:
- `proc_id` (string, required): Process ID
- `timeout_ms` (integer, optional, default=1000): Max wait time in ms (default 1000, max 10000)

### 23. linux_proc_stop
**Description**: Stop a managed process and clean up.
**Arguments**:
- `proc_id` (string, required): Process ID to stop
- `signal` (string, optional, default="TERM"): Signal to send (default TERM)

### 24. linux_fs_write
**Description**: Write or append text to a file. Supports atomic writes and SHA256 precondition checks.
**Arguments**:
- `path` (string, required): File path to write
- `content` (string, required): Text content to write
- `mode` (string, optional, default="rewrite"): rewrite or append
- `expected_sha256` (string, optional): If set, verify file hash before write

### 25. linux_fs_mkdir
**Description**: Create a directory (and parent directories if needed).
**Arguments**:
- `path` (string, required): Directory path to create
- `exist_ok` (boolean, optional, default=True)

### 26. linux_fs_move
**Description**: Move or rename a file or directory.
**Arguments**:
- `source` (string, required): Source path
- `dest` (string, required): Destination path

### 27. linux_fs_delete
**Description**: Delete a file or directory.
**Arguments**:
- `path` (string, required): Path to delete
- `recursive` (boolean, optional, default=False): Required for directories

### 28. linux_fs_edit
**Description**: Surgical text replacement in a file. Finds and replaces exact text matches.
**Arguments**:
- `path` (string, required): File to edit
- `old_text` (string, required): Text to find
- `new_text` (string, required): Replacement text
- `expected_replacements` (integer, optional, default=1): Expected match count

## Notes:
- Code execution mode would add `execute_code` tool (29th tool)
- Classic mode should expose all 28 tools
- Hybrid mode exposes subset based on config