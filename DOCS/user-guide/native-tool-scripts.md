# Native Tool Scripts

LLMC includes **executable tool scripts** that implement standard API specifications (OpenAI, MCP, Anthropic) for local execution. These allow local LLM models and MCP servers to use familiar tool interfaces without cloud dependencies.

---

## Overview

| Tool Category | Location | Description |
|---------------|----------|-------------|
| **OpenAI** | `scripts/openaitools/` | Responses API compatible (e.g., `file_search`) |
| **MCP** | `scripts/mcptools/` | MCP Filesystem spec (read, write, edit, search) |
| **Anthropic** | `scripts/anthropictools/` | Computer-use format (bash, text_editor) |
| **LLMC** | `scripts/llmctools/` | Graph-enriched native tools |

All tools:
- Accept **JSON input** via CLI argument or stdin
- Return **JSON output** to stdout
- Enforce **path containment** security
- Work standalone or integrated with MCP servers

---

## Quick Start

```bash
# Semantic search (OpenAI file_search)
./scripts/openaitools/file_search '{"query": "authentication", "limit": 5}'

# Read file (MCP read_text_file)
./scripts/mcptools/read_text_file '{"path": "README.md", "head": 20}'

# List directory (MCP list_directory)
./scripts/mcptools/list_directory '{"path": "src/"}'

# Execute shell command (Anthropic bash)
./scripts/anthropictools/bash '{"command": "git status"}'

# Run the demo to see all tools in action
python3 scripts/demo_native_tools.py
```

---

## OpenAI Tools

### `file_search`

Semantic search over codebase using LLMC RAG with optional enrichment.

**Path:** `scripts/openaitools/file_search`

**Input Schema:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | ✓ | — | Natural language search query |
| `limit` | integer | | 10 | Maximum results to return |
| `include_content` | boolean | | false | Include actual code snippets |
| `include_graph` | boolean | | true | Include callers/callees from graph |
| `include_enrichment` | boolean | | true | Include summaries, inputs, outputs, pitfalls |

**Example:**

```bash
./scripts/openaitools/file_search '{
  "query": "router configuration",
  "limit": 3,
  "include_content": true
}'
```

**Output:**

```json
{
  "success": true,
  "query": "router configuration",
  "results": [
    {
      "path": "llmc/routing/router.py",
      "symbol": "create_router",
      "kind": "function",
      "summary": "Creates a router instance based on config...",
      "score": 0.98,
      "normalized_score": 100.0,
      "lines": [38, 52],
      "content": "def create_router(config):\n    ...",
      "graph": {
        "node_id": "sym:router.create_router",
        "callers": ["sym:test_router.test_router_factory"],
        "callees": ["sym:router.DeterministicRouter"]
      },
      "enrichment": {
        "inputs": ["config: dict[str, Any]"],
        "outputs": ["Router instance"],
        "pitfalls": ["No error handling for invalid config"]
      }
    }
  ],
  "count": 1
}
```

---

## MCP Tools

### `read_text_file`

Read file contents as UTF-8 text.

**Path:** `scripts/mcptools/read_text_file`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | ✓ | File path to read |
| `head` | integer | | Read first N lines only |
| `tail` | integer | | Read last N lines only |

```bash
./scripts/mcptools/read_text_file '{"path": "README.md", "head": 10}'
```

### `write_file`

Create or overwrite a file.

**Path:** `scripts/mcptools/write_file`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | ✓ | File path to write |
| `content` | string | ✓ | Content to write |

```bash
./scripts/mcptools/write_file '{"path": "output.txt", "content": "Hello!"}'
```

### `list_directory`

List directory contents with `[FILE]`/`[DIR]` prefixes.

**Path:** `scripts/mcptools/list_directory`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | ✓ | Directory path |

```bash
./scripts/mcptools/list_directory '{"path": "src/"}'
```

**Output:**

```json
{
  "success": true,
  "entries": ["[FILE] main.py", "[DIR] utils/", "[FILE] config.py"],
  "count": 3
}
```

### `edit_file`

Make pattern-based edits (str_replace style).

**Path:** `scripts/mcptools/edit_file`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | ✓ | File path to edit |
| `edits` | array | ✓ | List of `{oldText, newText}` replacements |
| `dryRun` | boolean | | Preview changes without applying |

```bash
# Dry run (preview only)
./scripts/mcptools/edit_file '{
  "path": "config.py",
  "edits": [{"oldText": "DEBUG = False", "newText": "DEBUG = True"}],
  "dryRun": true
}'
```

### `search_files`

Recursively search for files matching a glob pattern.

**Path:** `scripts/mcptools/search_files`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | ✓ | Starting directory |
| `pattern` | string | ✓ | Glob pattern (e.g., `*.py`) |
| `excludePatterns` | array | | Patterns to exclude |

```bash
./scripts/mcptools/search_files '{
  "path": ".",
  "pattern": "test_*.py",
  "excludePatterns": ["__pycache__", ".venv"]
}'
```

---

## Anthropic Tools

### `bash`

Execute shell commands with security guardrails.

**Path:** `scripts/anthropictools/bash`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command` | string | ✓ | Shell command to execute |
| `timeout` | integer | | Timeout in seconds (default: 30) |
| `cwd` | string | | Working directory |

```bash
./scripts/anthropictools/bash '{"command": "git status"}'
```

**Security:**
- Dangerous commands (e.g., `rm -rf /`) are blocked
- Use `LLMC_ALLOWED_COMMANDS` to restrict allowed command prefixes

### `text_editor`

View and edit files with multiple commands.

**Path:** `scripts/anthropictools/text_editor`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command` | string | ✓ | `view`, `create`, `str_replace`, or `insert` |
| `path` | string | ✓ | File path |
| `view_range` | array | | `[start, end]` lines for `view` command |
| `content` | string | | Content for `create` or `insert` |
| `old_str` | string | | String to replace (`str_replace`) |
| `new_str` | string | | Replacement string (`str_replace`) |
| `insert_line` | integer | | Line number for `insert` |

```bash
# View with line numbers
./scripts/anthropictools/text_editor '{
  "command": "view",
  "path": "main.py",
  "view_range": [1, 50]
}'

# Replace string (must be unique)
./scripts/anthropictools/text_editor '{
  "command": "str_replace",
  "path": "config.py",
  "old_str": "DEBUG = False",
  "new_str": "DEBUG = True"
}'
```

---

## LLMC Tools

Symlinks to native LLMC CLIs with graph enrichment.

| Tool | Target | Description |
|------|--------|-------------|
| `mcgrep` | `llmc/mcgrep.py` | Semantic grep with RAG |
| `mcwho` | `llmc/mcwho.py` | Symbol relationship queries |

```bash
./scripts/llmctools/mcgrep "database connection"
./scripts/llmctools/mcwho who router.create_router
```

---

## Security

### Path Containment

All file operations validate paths against allowed roots:

```bash
export LLMC_ALLOWED_ROOTS="/home/user/project:/home/user/docs"
```

**Default:** Current working directory.

Attempts to access paths outside allowed roots fail with exit code 2:

```json
{
  "success": false,
  "error": "Path '/etc/passwd' is outside allowed roots: /home/user/project"
}
```

### Command Allowlist

Restrict `bash` tool to specific command prefixes:

```bash
export LLMC_ALLOWED_COMMANDS="git:ls:cat:grep"
```

### Dangerous Command Blocking

The following patterns are always blocked:
- `rm -rf /`
- Fork bombs
- Disk destruction commands

---

## Interface Contract

All native tool scripts follow this interface:

### Input

JSON object via CLI argument **or** piped to stdin:

```bash
# Argument style
./read_text_file '{"path": "foo.py"}'

# Stdin style
echo '{"path": "foo.py"}' | ./read_text_file
```

### Output

JSON to **stdout** (always, even for errors):

```json
{
  "success": true,
  "content": "...",
  "path": "/full/path"
}
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Execution completed (check `success` field) |
| 1 | JSON parse error or missing required arguments |
| 2 | Security violation (path traversal, blocked command) |

---

## Integration

### Python Integration

```python
from llmc_mcp.tools.native_scripts import file_search, bash, read_text_file
from pathlib import Path

repo = Path("/home/user/project")

# Semantic search
result = file_search("authentication", limit=5, repo_root=repo)
print(result["results"])

# Shell command
result = bash("git log -5 --oneline", repo_root=repo)
print(result["stdout"])

# File operations
result = read_text_file("README.md", repo_root=repo)
print(result["content"])
```

### MCP Server Integration

Register native tools with the MCP server:

```python
from llmc_mcp.tools.native_scripts import (
    call_native_tool,
    get_native_tool_definitions,
    NATIVE_TOOL_SCRIPTS,
)

# Get OpenAI-style tool definitions
definitions = get_native_tool_definitions()

# Call a tool
result = call_native_tool(
    "file_search",
    {"query": "authentication", "limit": 5},
    repo_root=Path("."),
)
```

---

## Configuration

Native tool scripts do not require configuration. They:

1. Use `LLMC_ALLOWED_ROOTS` environment variable for security
2. Connect to the local LLMC RAG index for `file_search`
3. Work standalone without any LLMC services running

---

## See Also

- [MCP Integration](../operations/mcp-integration.md)
- [RAG Search](./rag-search.md)
- [Tool Envelope](./tool-envelope.md)
