
# Implementation Notes — M5 Phase‑2
## Files
- `docker/Dockerfile`
- `docker/entrypoint.sh`
- `docker/.dockerignore`
- `deploy/mcp/docker-compose.yml`
- `deploy/mcp/llmc.toml.example`
- `scripts/smoke_te.sh`
- `scripts/smoke_mcp_in_container.sh`

## Commands
```
docker compose -f deploy/mcp/docker-compose.yml build
bash scripts/smoke_te.sh
bash scripts/smoke_mcp_in_container.sh   # CTRL+C to stop
```
If Claude Desktop uses `mcp.json`, set `command` to:
```
docker compose -f deploy/mcp/docker-compose.yml run --rm llmc-mcp
```

## Notes
- If your server module differs, edit `docker/entrypoint.sh`.
- Override env vars `LLMC_TE_*` as needed in compose.
