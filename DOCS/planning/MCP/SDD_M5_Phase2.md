
# SDD — M5 Phase‑2 (Docker + Compose + Entry)
**Scope:** Single container that runs MCP and TE; MCP talks to TE via subprocess. No network transport.

## Goals
- Reproducible container build (Python 3.11‑slim).
- `docker-compose` topology with bind mounts for workspace, logs, metrics.
- Entry script exporting LLMC_TE_* and starting MCP server on stdio.
- Keep repo root uncluttered: Dockerfile under `docker/`, compose under `deploy/mcp/`.

## Interfaces
- Image name: `llmc-mcp:dev`
- Compose service: `llmc-mcp`
- Volumes: `./logs`, `./metrics`, `./data`, repo bind to `/app`

## Claude Desktop (example)
You can point Claude MCP to this command:
```
docker compose -f deploy/mcp/docker-compose.yml run --rm llmc-mcp
```
Claude will talk over stdio (container keeps stdin/tty open).

## Risks
- Stdio over docker can be finicky on Windows; Linux/Mac OK.
- If your MCP server expects args, pass them via `command:` in compose.
