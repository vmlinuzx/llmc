# MCP Integration

LLMC implements the **Model Context Protocol (MCP)**, allowing it to serve as a powerful backend for Claude Desktop, IDEs, and other agents.

## What is MCP?
MCP is a standard for connecting LLMs to external data and tools. By running LLMC as an MCP server, you give Claude "eyes" into your local codebase.

## Configuration

To use LLMC with Claude Desktop, you need to add it to your `claude_desktop_config.json`.

**Location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux (unofficial): `~/.config/Claude/claude_desktop_config.json`

### Standard Setup (RAG Only)
This exposes search, graph, and lineage tools.

```json
{
  "mcpServers": {
    "llmc": {
      "command": "llmc-mcp",
      "args": [],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin:/home/user/.local/bin"
      }
    }
  }
}
```

### Hybrid Mode (RAG + Shell)
**⚠️ Warning: High Privilege**
This exposes **shell execution** capabilities (`run_command`), allowing Claude to run tests, git commands, etc. Use only if you trust the model.

```json
{
  "mcpServers": {
    "llmc": {
      "command": "llmc-mcp",
      "args": ["--hybrid"],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin"
      }
    }
  }
}
```

## Available Tools

Once connected, Claude will have access to:

| Tool | Description |
|------|-------------|
| `rag_search` | Semantic search over indexed code/docs. |
| `rag_where_used` | Find references to a function or class. |
| `rag_lineage` | Show upstream (callers) and downstream (dependencies). |
| `rag_status` | Check if the index is fresh. |
| `read_file` | Read file contents (safe mode). |

**Hybrid Mode Adds:**
| Tool | Description |
|------|-------------|
| `run_command` | Execute shell commands. |
| `write_file` | Create or edit files. |

## Troubleshooting

1.  **Logs**: Check Claude Desktop logs or LLMC logs in `~/.llmc/logs/mcp-server.log`.
2.  **Path Issues**: Ensure `llmc-mcp` is in your PATH, or provide the full absolute path in the JSON config (e.g., `/home/user/src/llmc/.venv/bin/llmc-mcp`).
3.  **Restart**: You must restart Claude Desktop after editing the config file.
