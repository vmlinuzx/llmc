# llmc-mcp

MCP server for Claude Desktop integration

**Module:** `llmc_mcp.cli`

## Usage

```text

 Usage: python -m llmc_mcp.cli [OPTIONS] COMMAND [ARGS]...

 LLMC MCP Server management CLI

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ start      Start the MCP daemon.                                             │
│ stop       Stop the MCP daemon.                                              │
│ restart    Restart the MCP daemon.                                           │
│ status     Show daemon status.                                               │
│ logs       Show daemon logs.                                                 │
│ show-key   Display the API key for connecting to the daemon.                 │
│ health     Quick health check (for scripts, exit code 0 = healthy).          │
╰──────────────────────────────────────────────────────────────────────────────╯

```
