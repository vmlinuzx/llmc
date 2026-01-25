# MCP Tool Reference

_Generated: 2025-12-16 16:14_

LLMC exposes **27 tools** via the Model Context Protocol.

## Tool Categories

| Category | Tools |
|----------|-------|
| get | `get_metrics` |
| linux | `linux_proc_list`, `linux_proc_kill`, `linux_sys_snapshot`, `linux_proc_start`, `linux_proc_send`, `linux_proc_read`, `linux_proc_stop`, `linux_fs_write`, `linux_fs_mkdir`, `linux_fs_move`, `linux_fs_delete`, `linux_fs_edit` |
| list | `list_dir` |
| other | `stat`, `inspect` |
| rag | `rag_search`, `rag_query`, `rag_search_enriched`, `rag_where_used`, `rag_lineage`, `rag_stats`, `rag_plan` |
| read | `read_file` |
| repo | `repo_read` |
| run | `run_cmd`, `run_rlm` |
| te | `te_run` |

---

## `get_metrics`

Get MCP server metrics (call counts, latencies, errors). Requires observability enabled.

_No parameters_

---

## `inspect`

Deep inspection of a file or symbol: snippet, graph relationships, and enrichment data.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | `string` |  | File path (relative to repo root) |
| `symbol` | `string` |  | Symbol name (e.g. 'MyClass.method') |
| `include_full_source` | `boolean` |  | Include full file source code (use sparingly) (default: `False`) |
| `max_neighbors` | `integer` |  | Max related entities to return per category (default: `3`) |

---

## `linux_fs_delete`

Delete a file or directory.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | `string` | ✓ | Path to delete |
| `recursive` | `boolean` |  | Required for directories (default: `False`) |

---

## `linux_fs_edit`

Surgical text replacement in a file. Finds and replaces exact text matches.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | `string` | ✓ | File to edit |
| `old_text` | `string` | ✓ | Text to find |
| `new_text` | `string` | ✓ | Replacement text |
| `expected_replacements` | `integer` |  | Expected match count (default: `1`) |

---

## `linux_fs_mkdir`

Create a directory (and parent directories if needed).

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | `string` | ✓ | Directory path to create |
| `exist_ok` | `boolean` |  | - (default: `True`) |

---

## `linux_fs_move`

Move or rename a file or directory.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `source` | `string` | ✓ | Source path |
| `dest` | `string` | ✓ | Destination path |

---

## `linux_fs_write`

Write or append text to a file. Supports atomic writes and SHA256 precondition checks.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | `string` | ✓ | File path to write |
| `content` | `string` | ✓ | Text content to write |
| `mode` | `string` |  | - Values: `['rewrite', 'append']` (default: `rewrite`) |
| `expected_sha256` | `string` |  | If set, verify file hash before write |

---

## `linux_proc_kill`

Send signal to a process. Safety guards prevent killing PID 1 or MCP server.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pid` | `integer` | ✓ | Process ID to signal |
| `signal` | `string` |  | Signal to send (default TERM) Values: `['TERM', 'KILL', 'INT', 'HUP', 'STOP', 'CONT']` (default: `TERM`) |

---

## `linux_proc_list`

List running processes with CPU/memory usage. Returns bounded results sorted by CPU.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `max_results` | `integer` |  | Maximum processes to return (1-5000, default 200) (default: `200`) |
| `user` | `string` |  | Optional username filter |

---

## `linux_proc_read`

Read output from a managed process with timeout.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `proc_id` | `string` | ✓ | Process ID |
| `timeout_ms` | `integer` |  | Max wait time in ms (default 1000, max 10000) (default: `1000`) |

---

## `linux_proc_send`

Send input to a managed process. Newline appended automatically.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `proc_id` | `string` | ✓ | Process ID from proc_start |
| `input` | `string` | ✓ | Text to send to the process |

---

## `linux_proc_start`

Start an interactive process/REPL. Returns proc_id for subsequent send/read/stop.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `command` | `string` | ✓ | Command to run (e.g. 'python -i', 'bash', 'node') |
| `cwd` | `string` |  | Working directory (optional) |
| `initial_read_timeout_ms` | `integer` |  | Time to wait for initial output (default 1000) (default: `1000`) |

---

## `linux_proc_stop`

Stop a managed process and clean up.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `proc_id` | `string` | ✓ | Process ID to stop |
| `signal` | `string` |  | Signal to send (default TERM) Values: `['TERM', 'KILL', 'INT', 'HUP']` (default: `TERM`) |

---

## `linux_sys_snapshot`

Get system resource snapshot: CPU, memory, disk usage, and load average.

_No parameters_

---

## `list_dir`

List contents of a directory. Returns files and subdirectories.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | `string` | ✓ | Absolute or relative path to directory |
| `max_entries` | `integer` |  | Maximum entries to return (default 1000) (default: `1000`) |
| `include_hidden` | `boolean` |  | Include hidden files (starting with .) (default: `False`) |

---

## `rag_lineage`

Trace symbol dependency lineage (upstream/downstream).

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `symbol` | `string` | ✓ | Symbol name to trace |
| `direction` | `string` |  | Trace direction: upstream (what calls this) or downstream (what this calls) Values: `['upstream', 'downstream', 'callers', 'callees']` (default: `downstream`) |
| `limit` | `integer` |  | Max results to return (default 50) (default: `50`) |

---

## `rag_plan`

Analyze query routing and retrieval plan without executing search. Shows how LLMC would handle the query.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | `string` | ✓ | Query to analyze |
| `detail_level` | `string` |  | Level of detail in response (default: summary) Values: `['summary', 'full']` (default: `summary`) |

---

## `rag_query`

Query the RAG system via the Tool Envelope.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | `string` | ✓ | The search query |
| `k` | `integer` |  | Number of results to return (default 5) |
| `index` | `string` |  | Specific index to query (optional) |
| `filters` | `object` |  | Metadata filters (optional) |

---

## `rag_search`

Search LLMC RAG index for relevant code/docs. Returns ranked snippets with provenance.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | `string` | ✓ | Natural language query or code concept to search for |
| `scope` | `string` |  | Search scope: repo (code), docs, or both Values: `['repo', 'docs', 'both']` (default: `repo`) |
| `limit` | `integer` |  | Max results to return (1-20) (default: `5`) |

---

## `rag_search_enriched`

Advanced RAG search with graph-based relationship enrichment. Supports multiple enrichment modes for semantic + relationship-aware retrieval.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | `string` | ✓ | Natural language query or code concept to search for |
| `limit` | `integer` |  | Max results to return (1-20) (default: `5`) |
| `enrich_mode` | `string` |  | Enrichment strategy: vector (semantic only), graph (relationships), hybrid (both), auto (intelligent routing) Values: `['vector', 'graph', 'hybrid', 'auto']` (default: `auto`) |
| `graph_depth` | `integer` |  | Relationship traversal depth (0-3). Higher values find more distant relationships (default: `1`) |
| `include_features` | `boolean` |  | Include enrichment quality metrics in response meta (default: `False`) |

---

## `rag_stats`

Get statistics about the RAG graph and enrichment coverage.

_No parameters_

---

## `rag_where_used`

Find where a symbol is used (callers, imports) across the codebase.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `symbol` | `string` | ✓ | Symbol name to find usages of |
| `limit` | `integer` |  | Max results to return (default 50) (default: `50`) |

---

## `read_file`

Read contents of a file. Returns text content with metadata.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | `string` | ✓ | Absolute or relative path to file |
| `max_bytes` | `integer` |  | Maximum bytes to read (default 1MB) (default: `1048576`) |

---

## `repo_read`

Read a file from a repository via the Tool Envelope.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `root` | `string` | ✓ | Root path of the repository |
| `path` | `string` | ✓ | Relative path to the file |
| `max_bytes` | `integer` |  | Maximum bytes to read (optional) |

---

## `run_cmd`

Execute a shell command with blacklist validation and timeout. Only approved binaries can run.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `command` | `string` | ✓ | Shell command to execute (blocked commands will be rejected) |
| `timeout` | `integer` |  | Max execution time in seconds (default 30) (default: `30`) |

---

## `stat`

Get file or directory metadata (size, timestamps, permissions).

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `path` | `string` | ✓ | Absolute or relative path |

---

## `te_run`

Execute a shell command through the Tool Envelope (TE) wrapper. Returns structured JSON output.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `args` | `array` | ✓ | Command arguments (e.g. ['grep', 'pattern', 'file']) |
| `cwd` | `string` |  | Optional working directory (must be within allowed roots) |
| `timeout` | `number` |  | Execution timeout in seconds |

---

## `run_rlm`

Run a Recursive Loop Manager (RLM) session to solve a complex task using Python code and available tools.

### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `goal` | `string` | ✓ | The goal or task for the RLM to solve. |
| `context` | `string` |  | Optional initial context (text or code) for the session. |
| `max_turns` | `integer` |  | Maximum number of turns (loops) allowed. |
