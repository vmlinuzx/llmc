# Multi-Repo Orchestration

Last updated: 2025-11-05

## Directory Strategy
- Keep the toolkit in `~/src/llmc_exec` (symlink `llmc_exec/` from this repo or clone directly).
- Each project repo maintains its own context artifacts (`CONTRACTS.md`, `AGENTS.md`, `.rag/`, `research/`, etc.).
- Logs and caches remain scoped to the target repo so concurrent runs do not collide.

## Quick Start
```bash
ln -s /home/vmlinux/src/llmc/llmc_exec ~/src/llmc_exec
export PATH="$HOME/src/llmc_exec/bin:$PATH"

# Run Codex against another repo
cd /home/vmlinux/src/my-project
llmc --repo "$(pwd)" codex "Implement feature toggle support"

# Refresh RAG for that repo hourly (cron)
0 * * * * llmc --repo /home/vmlinux/src/my-project refresh
```

## Environment Variables
- `LLMC_TARGET_REPO` — default repo when `--repo` is omitted.
- `LLMC_EXEC_ROOT` — overrides toolkit location if you relocate `llmc_exec`.
- `RAG_REFRESH_*`, `CODEX_WRAP_*`, etc. continue to work unchanged and apply to whichever repo you target.

## Notes
- `llmc codex` downgrades to local mode when deep-research triggers fire, regardless of which repo you target.
- `llmc ingest` can be run ad-hoc after you drop manual research notes; automation (`llmc refresh`) also calls it each tick.
- Python utilities (`tools.rag`, `tools.deep_research`) automatically add `LLMC_EXEC_ROOT` to `PYTHONPATH`, so you can invoke them from any repository without adjusting sys.path manually.
