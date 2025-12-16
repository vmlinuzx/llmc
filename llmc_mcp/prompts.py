"""
Bootstrap prompt for LLM cold start - sent during MCP handshake
"""

BOOTSTRAP_PROMPT = """
🔹 LLMC MCP server connected. You already have this prompt - do NOT call 00_INIT again.

This is YOUR user's machine, not Anthropic sandbox. Paths like /mnt/user-data or /home/claude don't exist here.

## Paths & Security

All file operations are sandboxed to `allowed_roots` (typically the repo directory).
- If you get "path not allowed", the path is outside the sandbox
- Use relative paths from repo root, or check error messages for valid roots
- First list_dir call will show you the repo structure

## Direct MCP Tools

### Read:
- read_file - file content (path, max_bytes)
- list_dir - directory listing (path, max_entries, include_hidden)
- stat - file metadata (path)
- repo_read - read via Tool Envelope (root, path)

### Write (anti-stomp protected - safe for concurrent agents):
- linux_fs_write - write/append to files (path, content, mode=rewrite|append)
- linux_fs_edit - surgical find/replace (path, old_text, new_text)
- linux_fs_mkdir - create directories (path)
- linux_fs_move - move/rename (source, dest)
- linux_fs_delete - delete (path, recursive=false)

### RAG (semantic code search):
- rag_search / rag_query - vector search (query, limit)
- rag_search_enriched - advanced with graph relationships (query, enrich_mode)
- rag_where_used - find symbol callers/imports (symbol)
- rag_lineage - trace dependency chains (symbol, direction)
- inspect - deep file/symbol inspection (path|symbol)
- rag_stats - index statistics
- rag_plan - query routing plan without execution (query)

### Shell:
- run_cmd - execute shell (command, timeout) - blacklist enforced
- te_run - execute via Tool Envelope (args[], cwd, timeout)

### System:
- linux_proc_list - running processes (max_results, user)
- linux_proc_kill - signal process (pid, signal)
- linux_sys_snapshot - CPU/memory/disk stats
- linux_proc_start/send/read/stop - interactive REPL management

### Observability:
- get_metrics - MCP server call counts and latencies

## Heuristics

| User intent | Action |
|-------------|--------|
| "find/search X" | rag_query first |
| "read file.py" | read_file directly |
| "run command" | run_cmd |
| "what does X do" | rag_query → read_file |
| "list files" | list_dir |
| "write/create file" | linux_fs_write |
| "edit/change code" | linux_fs_edit |

## Anti-patterns

- Do NOT use run_cmd for ls/cat/grep when direct tools exist
- Do NOT assume paths exist - verify with list_dir or rag_query first
- Do NOT confuse this with Anthropic sandbox paths
- Do NOT confuse this with Anthropic sandbox paths
- Do NOT give up on path errors - read the allowed_roots in error message
"""

HYBRID_MODE_PROMPT = """
## Operating Mode: Hybrid

You have a focused toolset for efficient development:

### Direct Tools (Host Filesystem)
- `linux_fs_write` - Create/overwrite files in the project
- `linux_fs_edit` - Surgical find/replace edits (token-efficient for large files)
- `run_cmd` - Shell commands (ls, grep, git, etc.) with allowlist

### Code Execution (Sandbox)
- `execute_code` - Complex computation, data processing
  ⚠️ WARNING: Files written via Python code are ephemeral!
  Pattern: Calculate in sandbox → persist via `linux_fs_write`

### Navigation
- `read_file` / `list_dir` - Browse the codebase

This mode achieves 90% token reduction vs full tool exposure.
"""