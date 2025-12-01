
# Agent Implementation Prompt — M5 Phase‑2 (Copy/Paste)
Objective: Add containerization for MCP+TE with Dockerfile, compose, and entrypoint.

## Git Flow
```
git checkout -b feat/m5-phase2-docker
```

## Add Files
- `docker/Dockerfile`
- `docker/entrypoint.sh`
- `docker/.dockerignore`
- `deploy/mcp/docker-compose.yml`
- `deploy/mcp/llmc.toml.example`
- `scripts/smoke_te.sh`
- `scripts/smoke_mcp_in_container.sh`
- `DOCS/planning/MCP/SDD_M5_Phase2.md`
- `DOCS/planning/MCP/IMPL_SDD_M5_Phase2.md`
- `DOCS/planning/MCP/IMPLEMENT_PROMPT_M5_Phase2.md` (this file)

## Build & Test
```
docker compose -f deploy/mcp/docker-compose.yml build
bash scripts/smoke_te.sh
```
If tests pass, open PR:
```
git add .
git commit -m "M5 Phase-2: Dockerfile + compose + entrypoint for single-container MCP+TE"
git push origin feat/m5-phase2-docker
```
