# Operations

Guides for running and monitoring LLMC in production.

---

## In This Section

| Guide | Description |
|-------|-------------|
| [RAG Daemon](daemon.md) | Service lifecycle, systemd integration |
| [MCP Integration](mcp-integration.md) | Claude Desktop setup |
| [Troubleshooting](troubleshooting.md) | Common issues and fixes |

---

## Quick Commands

```bash
# Start the RAG service
llmc-cli service start

# Check status
llmc-cli service status

# View logs
llmc-cli service logs -f

# Health check
llmc-cli debug doctor
```

---

## Key Concepts

- **Daemon**: Long-running process that keeps indexes fresh
- **Health checks**: Validate database, embeddings, and enrichment state
- **MCP**: Model Context Protocol for LLM tool integration

---

## Data Locations

| Location | Contents |
|----------|----------|
| `~/.llmc/` | Global config, repo registry |
| `.llmc/` (per repo) | Database, embeddings, graph |
| `~/.llmc/logs/` | Service logs |
