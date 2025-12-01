
# LLMC — M5 Phase‑2 Patch Bundle
Dockerize the single-container MCP+TE setup with a clean layout (no root clutter).

## Apply
Copy into repo, then:
```
docker compose -f deploy/mcp/docker-compose.yml build
bash scripts/smoke_te.sh
```
Use `docker compose ... run --rm llmc-mcp` as the MCP command in Claude Desktop.
