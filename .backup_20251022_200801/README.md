# Codex Orchestration Template

This is a drop-in template to bootstrap new projects with the same local-first LLM orchestration, context management, and helper scripts used here.

Included
- AGENTS.md: Orchestration system, tools, usage
- CONTRACTS.md: Compact operating contract and testing rules
- .clinerules: Quick reference for commands and constraints
- .codexignore: Sync exclusions (for Google Drive, etc.)
- scripts/: Local-first LLM gateway, smart routing wrapper, drive sync script

Quick Start
1) Copy the `template/` folder contents into your new repo root
2) Make scripts executable:
   - `chmod +x scripts/*.sh`
3) (Optional) Set `GEMINI_API_KEY` in `.env.local` for API fallback
4) Try a local generation:
   - `./scripts/codex_wrap.sh --local "write hello world in python"`

Drive Sync
- `./scripts/sync_to_drive.sh` runs silently in background
- Destination defaults to `/mnt/g/My Drive/<repo-name>`
- Use `-v` for verbose and `-n` for dry-run

