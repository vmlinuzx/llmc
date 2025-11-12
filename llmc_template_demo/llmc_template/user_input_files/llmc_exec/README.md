# LLMC Exec Toolkit

Shared orchestration toolkit for running Codex/Beatrice, RAG refresh, and deep research workflows against any codebase.

## Layout
- `bin/` — entrypoint scripts (`llmc`) for dispatching commands with repo-specific overrides.
- `llmc_template/config/` — default configuration (service quotas, routing presets).
- `templates/` — reusable note templates and onboarding snippets.

## Setup
- Optional: symlink the toolkit for global use
  ```bash
  mkdir -p ~/src
  ln -s "$(pwd)/llmc_exec" ~/src/llmc_exec
  export PATH="~/src/llmc_exec/bin:$PATH"
  ```
- Set `LLMC_EXEC_ROOT` if you relocate the toolkit; otherwise `bin/llmc` infers it automatically.

## Usage
- Target the current directory: `llmc codex` or `llmc refresh`.
- Explicit repo: `llmc --repo /path/to/project codex --local`.
- Supported subcommands:
  - `codex` — run `codex_wrap.sh` with all multi-tier routing features.
  - `refresh` — execute `rag_refresh_cron.sh` once (includes deep-research ingest).
  - `rag-sync` — sync specific files: `llmc --repo /repo rag-sync src/foo.py docs/*.md`.
  - `ingest` — move notes from `research/incoming/` into the archive.
  - `gateway` — call `llm_gateway.sh` directly for low-level prompts.

The toolkit expects a `LLMC_TARGET_REPO` environment variable or `--repo` flag pointing to the repository you want to operate on. Each target repo should contain its own `CONTRACTS.md`, `AGENTS.md`, `.rag/` directory, and other context files. Logs and derived artifacts stay inside the selected repository.
