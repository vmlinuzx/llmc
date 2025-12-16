# MCP Tool Reference

Reference documentation for all available MCP tools.

## `get_metrics`
Get MCP server metrics (call counts, latencies, errors). Requires observability enabled.

### Arguments
_No arguments._

---

## `inspect`
Deep inspection of a file or symbol: snippet, graph relationships, and enrichment data.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | No | File path (relative to repo root) |
| `symbol` | `string` | No | Symbol name (e.g. 'MyClass.method') |
| `include_full_source` | `boolean` | No | Include full file source code (use sparingly) (Default: `False`) |
| `max_neighbors` | `integer` | No | Max related entities to return per category (Default: `3`) |

---

## `linux_fs_delete`
Delete a file or directory.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | Path to delete |
| `recursive` | `boolean` | No | Required for directories (Default: `False`) |

---

## `linux_fs_edit`
Surgical text replacement in a file. Finds and replaces exact text matches.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | File to edit |
| `old_text` | `string` | Yes | Text to find |
| `new_text` | `string` | Yes | Replacement text |
| `expected_replacements` | `integer` | No | Expected match count (Default: `1`) |

---

## `linux_fs_mkdir`
Create a directory (and parent directories if needed).

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | Directory path to create |
| `exist_ok` | `boolean` | No | - (Default: `True`) |

---

## `linux_fs_move`
Move or rename a file or directory.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `source` | `string` | Yes | Source path |
| `dest` | `string` | Yes | Destination path |

---

## `linux_fs_write`
Write or append text to a file. Supports atomic writes and SHA256 precondition checks.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | File path to write |
| `content` | `string` | Yes | Text content to write |
| `mode` | `string` | No | - Allowed: `['rewrite', 'append']` (Default: `rewrite`) |
| `expected_sha256` | `string` | No | If set, verify file hash before write |

---

## `linux_proc_kill`
Send signal to a process. Safety guards prevent killing PID 1 or MCP server.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `pid` | `integer` | Yes | Process ID to signal |
| `signal` | `string` | No | Signal to send (default TERM) Allowed: `['TERM', 'KILL', 'INT', 'HUP', 'STOP', 'CONT']` (Default: `TERM`) |

---

## `linux_proc_list`
List running processes with CPU/memory usage. Returns bounded results sorted by CPU.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `max_results` | `integer` | No | Maximum processes to return (1-5000, default 200) (Default: `200`) |
| `user` | `string` | No | Optional username filter |

---

## `linux_proc_read`
Read output from a managed process with timeout.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `proc_id` | `string` | Yes | Process ID |
| `timeout_ms` | `integer` | No | Max wait time in ms (default 1000, max 10000) (Default: `1000`) |

---

## `linux_proc_send`
Send input to a managed process. Newline appended automatically.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `proc_id` | `string` | Yes | Process ID from proc_start |
| `input` | `string` | Yes | Text to send to the process |

---

## `linux_proc_start`
Start an interactive process/REPL. Returns proc_id for subsequent send/read/stop.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `command` | `string` | Yes | Command to run (e.g. 'python -i', 'bash', 'node') |
| `cwd` | `string` | No | Working directory (optional) |
| `initial_read_timeout_ms` | `integer` | No | Time to wait for initial output (default 1000) (Default: `1000`) |

---

## `linux_proc_stop`
Stop a managed process and clean up.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `proc_id` | `string` | Yes | Process ID to stop |
| `signal` | `string` | No | Signal to send (default TERM) Allowed: `['TERM', 'KILL', 'INT', 'HUP']` (Default: `TERM`) |

---

## `linux_sys_snapshot`
Get system resource snapshot: CPU, memory, disk usage, and load average.

### Arguments
_No arguments._

---

## `list_dir`
List contents of a directory. Returns files and subdirectories.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | Absolute or relative path to directory |
| `max_entries` | `integer` | No | Maximum entries to return (default 1000) (Default: `1000`) |
| `include_hidden` | `boolean` | No | Include hidden files (starting with .) (Default: `False`) |

---

## `rag_lineage`
Trace symbol dependency lineage (upstream/downstream).

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `symbol` | `string` | Yes | Symbol name to trace |
| `direction` | `string` | No | Trace direction: upstream (what calls this) or downstream (what this calls) Allowed: `['upstream', 'downstream', 'callers', 'callees']` (Default: `downstream`) |
| `limit` | `integer` | No | Max results to return (default 50) (Default: `50`) |

---

## `rag_plan`
Analyze query routing and retrieval plan without executing search. Shows how LLMC would handle the query.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `query` | `string` | Yes | Query to analyze |
| `detail_level` | `string` | No | Level of detail in response (default: summary) Allowed: `['summary', 'full']` (Default: `summary`) |

---

## `rag_query`
Query the RAG system via the Tool Envelope.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `query` | `string` | Yes | The search query |
| `k` | `integer` | No | Number of results to return (default 5) |
| `index` | `string` | No | Specific index to query (optional) |
| `filters` | `object` | No | Metadata filters (optional) |

---

## `rag_search`
Search LLMC RAG index for relevant code/docs. Returns ranked snippets with provenance.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `query` | `string` | Yes | Natural language query or code concept to search for |
| `scope` | `string` | No | Search scope: repo (code), docs, or both Allowed: `['repo', 'docs', 'both']` (Default: `repo`) |
| `limit` | `integer` | No | Max results to return (1-20) (Default: `5`) |

---

## `rag_search_enriched`
Advanced RAG search with graph-based relationship enrichment. Supports multiple enrichment modes for semantic + relationship-aware retrieval.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `query` | `string` | Yes | Natural language query or code concept to search for |
| `limit` | `integer` | No | Max results to return (1-20) (Default: `5`) |
| `enrich_mode` | `string` | No | Enrichment strategy: vector (semantic only), graph (relationships), hybrid (both), auto (intelligent routing) Allowed: `['vector', 'graph', 'hybrid', 'auto']` (Default: `auto`) |
| `graph_depth` | `integer` | No | Relationship traversal depth (0-3). Higher values find more distant relationships (Default: `1`) |
| `include_features` | `boolean` | No | Include enrichment quality metrics in response meta (Default: `False`) |

---

## `rag_stats`
Get statistics about the RAG graph and enrichment coverage.

### Arguments
_No arguments._

---

## `rag_where_used`
Find where a symbol is used (callers, imports) across the codebase.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `symbol` | `string` | Yes | Symbol name to find usages of |
| `limit` | `integer` | No | Max results to return (default 50) (Default: `50`) |

---

## `read_file`
Read contents of a file. Returns text content with metadata.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | Absolute or relative path to file |
| `max_bytes` | `integer` | No | Maximum bytes to read (default 1MB) (Default: `1048576`) |

---

## `repo_read`
Read a file from a repository via the Tool Envelope.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `root` | `string` | Yes | Root path of the repository |
| `path` | `string` | Yes | Relative path to the file |
| `max_bytes` | `integer` | No | Maximum bytes to read (optional) |

---

## `run_cmd`
Execute a shell command with blacklist validation and timeout. Only approved binaries can run.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `command` | `string` | Yes | Shell command to execute (blocked commands will be rejected) |
| `timeout` | `integer` | No | Max execution time in seconds (default 30) (Default: `30`) |

---

## `stat`
Get file or directory metadata (size, timestamps, permissions).

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `path` | `string` | Yes | Absolute or relative path |

---

## `te_run`
Execute a shell command through the Tool Envelope (TE) wrapper. Returns structured JSON output.

### Arguments
| Name | Type | Required | Description |
|---|---|---|---|
| `args` | `array` | Yes | Command arguments (e.g. ['grep', 'pattern', 'file']) |
| `cwd` | `string` | No | Optional working directory (must be within allowed roots) |
| `timeout` | `number` | No | Execution timeout in seconds |

---
