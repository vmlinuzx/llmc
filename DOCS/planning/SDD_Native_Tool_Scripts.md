# SDD: Native Tool Scripts — Training-Aligned Tool Interfaces

**Date:** 2025-12-20  
**Author:** Dave + Antigravity  
**Status:** Ready for Implementation  
**Priority:** P0 🔥  
**Effort:** 8-12 hours  

---

## 1. Executive Summary

**Primary Goal:** Implement the **OpenAI tool specification exactly** as executable scripts, so any tool-calling framework (local models, MCP servers, agents) can use them without adaptation layers.

**Secondary Benefit:** LLMs like Qwen, GPT-4, and Claude were *trained* on these exact tool names and signatures. Matching the spec means zero prompting overhead — the model's training data IS the documentation.

### The Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Tool Consumers                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Boxxie/Qwen  │  │ MCP Server   │  │ Claude Desktop   │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
│         │                 │                   │             │
│         └────────────────┬┴──────────────────┘             │
│                          ▼                                  │
│              ┌───────────────────────┐                      │
│              │ scripts/openaitools/  │ ← OpenAI spec       │
│              │ scripts/mcptools/     │ ← MCP spec          │
│              └───────────┬───────────┘                      │
│                          │                                  │
│                          ▼                                  │
│              ┌───────────────────────┐                      │
│              │ LLMC RAG / Filesystem │                      │
│              └───────────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

**Result:** One implementation, multiple consumers. JSON in, JSON out.

---

## 2. Problem Statement

### Current State

LLMC agents (Boxxie, MCP server) define tools in:
1. **Python code** (llmc_mcp/tools/*.py)
2. **Bootstrap prompts** (5-10KB of tool definitions)
3. **Runtime schemas** (JSON schema generation)

This creates:
- **Token waste** — Every conversation pays the tool definition tax
- **Documentation drift** — Prompts lie about capabilities
- **Training mismatch** — Our tool names don't match what models were trained on
- **Complexity** — Multiple abstraction layers between "user wants X" and "X happens"

### Desired State

```
scripts/
├── mcptools/           # Official MCP spec (Claude Desktop compatible)
│   ├── read_text_file
│   ├── write_file
│   ├── edit_file
│   ├── list_directory
│   ├── search_files
│   └── ...
│
├── anthropictools/     # Claude computer-use format  
│   ├── bash
│   └── text_editor
│
└── openaitools/        # OpenAI function calling format
    ├── file_search
    └── run_command
```

Each script:
- **Name matches training data exactly**
- **JSON in, JSON out**
- **Executable standalone** (`./read_text_file '{"path": "foo.py"}'`)
- **Can be called by MCP server, agents, or humans**

---

## 3. Architecture

### 3.1 Directory Structure

```
scripts/
├── mcptools/                    # Primary — Official MCP filesystem spec
│   ├── read_text_file           # Read file as UTF-8 text
│   ├── read_multiple_files      # Batch read
│   ├── write_file               # Create/overwrite file
│   ├── edit_file                # Pattern-based edits (like str_replace)
│   ├── create_directory         # mkdir -p
│   ├── list_directory           # ls with [FILE]/[DIR] prefixes
│   ├── move_file                # mv (rename)
│   ├── search_files             # Recursive glob search
│   ├── directory_tree           # JSON tree structure
│   ├── get_file_info            # stat (metadata)
│   └── README.md                # Tool documentation
│
├── anthropictools/              # Claude computer-use format
│   ├── bash                     # Shell command execution
│   ├── text_editor              # Multi-command editor (view/create/str_replace/insert)
│   └── README.md
│
├── openaitools/                 # OpenAI Responses API format
│   ├── file_search              # → wraps mcgrep
│   ├── web_search               # → stub or real implementation
│   ├── code_interpreter         # → subprocess Python execution
│   └── README.md
│
└── llmctools/                   # LLMC-native (graph-enriched)
    ├── mcgrep                   # → symlink to llmc/mcgrep.py
    ├── mcread                   # → symlink to llmc mcread
    ├── mcwho                    # → symlink to llmc mcwho
    └── mcinspect                # → symlink to llmc mcinspect
```

### 3.2 Script Interface Contract

**Input:** JSON object as first CLI argument, OR piped to stdin

```bash
# Argument style
./read_text_file '{"path": "src/main.py"}'

# Stdin style
echo '{"path": "src/main.py"}' | ./read_text_file
```

**Output:** JSON to stdout

```json
{
  "success": true,
  "content": "#!/usr/bin/env python3\n...",
  "path": "src/main.py",
  "size": 1234
}
```

**Errors:** JSON to stdout (not stderr, for LLM parsing)

```json
{
  "success": false,
  "error": "File not found: src/main.py"
}
```

**Exit codes:**
- `0` — Success (check `success` field for semantic success)
- `1` — JSON parse error or missing required args
- `2` — Security violation (path traversal, etc.)

### 3.3 Security Model

Each script validates:

1. **Path containment** — All paths must resolve within allowed roots
2. **No shell injection** — Arguments are never passed through shell
3. **Configurable roots** — Read `LLMC_ALLOWED_ROOTS` env var or `.llmc/config`

```bash
# Example security check at top of each script
ALLOWED_ROOTS="${LLMC_ALLOWED_ROOTS:-$(pwd)}"
# Validate path is under allowed roots before any operation
```

---

## 4. Tool Specifications

### 4.1 MCP Tools (Primary)

Based on official MCP Filesystem Server specification.

#### `read_text_file`

```json
{
  "name": "read_text_file",
  "description": "Read complete contents of a file as UTF-8 text",
  "input": {
    "path": "string (required)",
    "head": "number (optional) - first N lines",
    "tail": "number (optional) - last N lines"
  },
  "output": {
    "success": "boolean",
    "content": "string",
    "path": "string",
    "lines": "number"
  }
}
```

#### `write_file`

```json
{
  "name": "write_file", 
  "description": "Create new file or overwrite existing",
  "input": {
    "path": "string (required)",
    "content": "string (required)"
  },
  "output": {
    "success": "boolean",
    "path": "string",
    "bytes_written": "number"
  }
}
```

#### `edit_file`

```json
{
  "name": "edit_file",
  "description": "Make selective edits using pattern matching",
  "input": {
    "path": "string (required)",
    "edits": [
      {
        "oldText": "string - text to find",
        "newText": "string - replacement text"
      }
    ],
    "dryRun": "boolean (default: false)"
  },
  "output": {
    "success": "boolean",
    "edits_applied": "number",
    "diff": "string (if dryRun)"
  }
}
```

#### `list_directory`

```json
{
  "name": "list_directory",
  "description": "List directory contents with [FILE] or [DIR] prefixes",
  "input": {
    "path": "string (required)"
  },
  "output": {
    "success": "boolean",
    "entries": ["[FILE] foo.py", "[DIR] src/", "..."]
  }
}
```

#### `search_files`

```json
{
  "name": "search_files",
  "description": "Recursively search for files matching pattern",
  "input": {
    "path": "string (required) - starting directory",
    "pattern": "string (required) - glob pattern",
    "excludePatterns": ["string"] 
  },
  "output": {
    "success": "boolean",
    "matches": ["path/to/file1.py", "path/to/file2.py"]
  }
}
```

### 4.2 Anthropic Tools

#### `bash`

```json
{
  "name": "bash",
  "description": "Execute shell command in persistent bash session",
  "input": {
    "command": "string (required)"
  },
  "output": {
    "success": "boolean",
    "stdout": "string",
    "stderr": "string",
    "exit_code": "number"
  }
}
```

#### `text_editor`

```json
{
  "name": "text_editor",
  "description": "View and modify text files",
  "input": {
    "command": "view | create | str_replace | insert",
    "path": "string (required)",
    "content": "string (for create)",
    "old_str": "string (for str_replace)",
    "new_str": "string (for str_replace)",
    "insert_line": "number (for insert)",
    "view_range": [start, end] 
  },
  "output": {
    "success": "boolean",
    "content": "string (for view)",
    "message": "string"
  }
}
```

### 4.3 OpenAI Tools

#### `file_search`

```json
{
  "name": "file_search",
  "description": "Semantic search over codebase (RAG)",
  "input": {
    "query": "string (required)",
    "limit": "number (default: 10)"
  },
  "output": {
    "success": "boolean",
    "results": [
      {
        "path": "string",
        "snippet": "string", 
        "score": "number",
        "lines": [start, end]
      }
    ]
  }
}
```

**Implementation:** Wraps `mcgrep --json`

---

## 5. Implementation Plan

### Phase 1: Core Tools ✅ COMPLETE

| Script | Status | Wraps |
|--------|--------|-------|
| `openaitools/file_search` | ✅ Done | LLMC RAG `search_spans` |
| `mcptools/read_text_file` | ✅ Done | Raw file read |
| `mcptools/write_file` | ✅ Done | Raw file write |
| `mcptools/list_directory` | ✅ Done | `pathlib.iterdir` |

### Phase 2: LLMC Enrichment ✅ COMPLETE

`file_search` now includes full LLMC enrichment:

| Enhancement | Status |
|-------------|--------|
| Graph context | ✅ Callers/callees from `rag_graph.json` |
| Enrichment data | ✅ Summaries, inputs/outputs, pitfalls |
| File content | ✅ Optional code snippets via `include_content` |
| Routing info | ✅ Via debug mode in `search_spans` |

### Phase 3: Additional Tools ✅ COMPLETE

| Script | Status | Wraps |
|--------|--------|-------|
| `mcptools/edit_file` | ✅ Done | str_replace pattern editing |
| `mcptools/search_files` | ✅ Done | `pathlib.rglob` + fnmatch |
| `anthropictools/bash` | ✅ Done | `subprocess.run` with security |
| `anthropictools/text_editor` | ✅ Done | view/create/str_replace/insert |
| `llmctools/mcgrep` | ✅ Done | Symlink to llmc/mcgrep.py |
| `llmctools/mcwho` | ✅ Done | Symlink to llmc/mcwho.py |

### Phase 4: Integration (TODO)

- [ ] Update MCP server to delegate to scripts
- [ ] Update Boxxie agent to use script paths
- [ ] Test with Qwen, Claude, GPT-4

---

## 6. Usage Examples

### Direct CLI

```bash
# Read a file
./scripts/mcptools/read_text_file '{"path": "llmc/router.py"}'

# Edit a file (dry run first)
./scripts/mcptools/edit_file '{
  "path": "config.py",
  "edits": [{"oldText": "DEBUG = False", "newText": "DEBUG = True"}],
  "dryRun": true
}'

# Semantic search
./scripts/openaitools/file_search '{"query": "authentication middleware", "limit": 5}'
```

### Agent Integration

```python
# In agent system prompt:
"""
You have access to tools in scripts/mcptools/:
- read_text_file, write_file, list_directory, edit_file, search_files

Call them with JSON arguments. Example:
<tool>read_text_file</tool>
<args>{"path": "README.md"}</args>
"""

# Agent execution loop:
result = subprocess.run(
    [f"scripts/mcptools/{tool_name}", json.dumps(args)],
    capture_output=True, text=True
)
return json.loads(result.stdout)
```

### MCP Server Integration

```python
# In llmc_mcp/server.py:
async def handle_tool_call(name: str, args: dict) -> dict:
    script_path = TOOL_SCRIPTS.get(name)
    if script_path:
        result = subprocess.run(
            [script_path, json.dumps(args)],
            capture_output=True, text=True
        )
        return json.loads(result.stdout)
    # Fall back to Python implementation
    return await legacy_tool_handlers[name](args)
```

---

## 7. Success Criteria

- [ ] All MCP core tools (read, write, list, edit, search) implemented
- [ ] `bash` tool works with security sandboxing
- [ ] `file_search` wraps mcgrep successfully
- [ ] Qwen can use tools with zero tool definition prompting
- [ ] MCP server delegates to scripts
- [ ] All tools have consistent JSON in/out interface
- [ ] Security validation passes (no path traversal)

---

## 8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Shell scripts are slower than Python | Medium | Low | Scripts are thin wrappers; latency acceptable for AI use |
| Path traversal attacks | Medium | High | Validate all paths against LLMC_ALLOWED_ROOTS |
| JSON parsing edge cases | Low | Medium | Use `jq` or Python for robust parsing |
| Models don't recognize tool names | Low | High | Names are from official specs; fallback to prompting |

---

## 9. Files Created

| Path | Description |
|------|-------------|
| `scripts/mcptools/read_text_file` | Read UTF-8 file |
| `scripts/mcptools/write_file` | Write file |
| `scripts/mcptools/edit_file` | Pattern-based editing |
| `scripts/mcptools/list_directory` | List dir contents |
| `scripts/mcptools/search_files` | Glob search |
| `scripts/mcptools/create_directory` | mkdir -p |
| `scripts/mcptools/move_file` | mv/rename |
| `scripts/mcptools/get_file_info` | File metadata |
| `scripts/mcptools/directory_tree` | JSON tree |
| `scripts/anthropictools/bash` | Shell execution |
| `scripts/anthropictools/text_editor` | Multi-command editor |
| `scripts/openaitools/file_search` | Semantic search wrapper |
| `scripts/README.md` | Usage documentation |

---

## 10. Notes

This is the **nuclear option** for tool integration. Instead of building adapters, parsers, and protocol translators, we're saying: "The model already knows the API. Let's just implement it."

The training data IS the documentation. The tool name IS the prompt.

**Key insight from Dave:** "Prompting becomes training. Utilize OpenAI MCP tools under this folder, or Anthropic tools under this folder, whichever your training works best with."

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2025-12-20 | Dave + Antigravity | Initial draft |
