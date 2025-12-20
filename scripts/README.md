# Native Tool Scripts

**OpenAI/Anthropic/MCP-compatible tool interfaces for local execution.**

These scripts implement standard tool APIs as standalone executables. They can be called by:
- Local LLM agents (Boxxie/Qwen via Ollama)
- MCP servers (Claude Desktop compatible)
- Shell scripts / CLI

## Quick Start

```bash
# OpenAI file_search (semantic RAG with LLMC enrichment)
./scripts/openaitools/file_search '{"query": "authentication", "limit": 5}'
./scripts/openaitools/file_search '{"query": "router", "include_content": true}'

# MCP Filesystem tools
./scripts/mcptools/read_text_file '{"path": "src/main.py"}'
./scripts/mcptools/read_text_file '{"path": "README.md", "head": 20}'
./scripts/mcptools/write_file '{"path": "output.txt", "content": "Hello!"}'
./scripts/mcptools/list_directory '{"path": "src/"}'
./scripts/mcptools/edit_file '{"path": "config.py", "edits": [{"oldText": "DEBUG=False", "newText": "DEBUG=True"}]}'
./scripts/mcptools/search_files '{"path": ".", "pattern": "*.py"}'

# Anthropic computer-use tools
./scripts/anthropictools/bash '{"command": "git status"}'
./scripts/anthropictools/text_editor '{"command": "view", "path": "main.py", "view_range": [1, 50]}'
./scripts/anthropictools/text_editor '{"command": "str_replace", "path": "main.py", "old_str": "foo", "new_str": "bar"}'
```

## Directory Structure

```
scripts/
├── openaitools/        # OpenAI Responses API format
│   └── file_search     # Semantic RAG search with LLMC enrichment
│
├── mcptools/           # MCP Filesystem spec
│   ├── read_text_file  # Read UTF-8 file (with head/tail)
│   ├── write_file      # Create/overwrite file
│   ├── list_directory  # List with [FILE]/[DIR] prefixes
│   ├── edit_file       # Pattern-based str_replace editing
│   └── search_files    # Recursive glob search
│
├── anthropictools/     # Anthropic computer-use format
│   ├── bash            # Shell command execution
│   └── text_editor     # view/create/str_replace/insert
│
└── llmctools/          # LLMC-native (graph-enriched)
    ├── mcgrep          # → symlink to llmc/mcgrep.py
    └── mcwho           # → symlink to llmc/mcwho.py
```

## Interface Contract

**Input:** JSON object as CLI argument or piped to stdin

```bash
# Argument style
./read_text_file '{"path": "foo.py"}'

# Stdin style  
echo '{"path": "foo.py"}' | ./read_text_file
```

**Output:** JSON to stdout

```json
{
  "success": true,
  "content": "...",
  "path": "/full/path/to/file"
}
```

**Errors:** JSON to stdout (for LLM parsing)

```json
{
  "success": false,
  "error": "File not found: foo.py"
}
```

**Exit codes:**
- `0` — Success (check `success` field)
- `1` — JSON parse error or missing args
- `2` — Security violation (path traversal)

## Security

### Path Containment
All file operations validate paths against `LLMC_ALLOWED_ROOTS`:

```bash
export LLMC_ALLOWED_ROOTS="/home/user/project:/home/user/docs"
```

Default: current working directory.

### Command Allowlist (bash tool)
For the `bash` tool, use `LLMC_ALLOWED_COMMANDS` to restrict commands:

```bash
export LLMC_ALLOWED_COMMANDS="git:ls:cat:grep"
```

Dangerous commands (rm -rf /, fork bombs, etc.) are always blocked.

## LLMC Enrichment (file_search)

The `file_search` tool includes optional LLMC-specific enrichment:

```bash
./scripts/openaitools/file_search '{
  "query": "authentication",
  "limit": 5,
  "include_content": true,    # Include actual code snippets
  "include_graph": true,      # Include callers/callees from graph
  "include_enrichment": true  # Include inputs/outputs/pitfalls
}'
```

Example enriched result:
```json
{
  "path": "llmc/routing/router.py",
  "symbol": "create_router",
  "kind": "function",
  "summary": "Creates a router instance...",
  "score": 0.98,
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
```
