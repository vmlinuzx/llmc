# LLMC RAG Utilities

This repo hosts the LLMC RAG tooling stack: a small set of CLIs and services that keep project repos indexed, enriched, and queryable via RAG, plus the contracts/docs that drive agent behavior.

The three primary “front door” commands are:

- `llmc-rag-repo` – manage which repos are registered for RAG.
- `llmc-rag-daemon` – low-level scheduler/worker loop to keep workspaces fresh.
- `llmc-rag-service` – high-level human-facing service wrapper.

All three live under `scripts/` and are thin Python shims into the `tools.*` modules.

## Prerequisites

- Python 3.12 (or compatible) with a virtualenv:

```bash
cd ~/src/llmc
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[rag]"
```

To make the CLIs feel like real commands, add the scripts directory to your `PATH`:

```bash
echo 'export PATH="$HOME/src/llmc/scripts:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

After that you can run `llmc-rag-*` directly from any shell.

## llmc-rag-repo – Repo Registry UX

Backed by `python -m tools.rag_repo.cli`.

Manages the global repo registry (`~/.llmc/repos.yml`) and per-repo `.llmc/rag` workspaces.

```bash
llmc-rag-repo           # tree-style help
llmc-rag-repo add /home/you/src/llmc
llmc-rag-repo list --json
llmc-rag-repo inspect /home/you/src/llmc
```

Key behaviors:

- Normalizes paths and creates `.llmc/rag` as needed.
- Writes/reads `~/.llmc/repos.yml` via a YAML registry adapter.
- Never explodes with a stacktrace on bad input; prints a short error + help.

## llmc-rag-daemon – Scheduler / Worker UX

Backed by `python -m tools.rag_daemon.main`.

Runs the scheduler loop that keeps registered repos fresh.

```bash
llmc-rag-daemon                  # tree-style help
llmc-rag-daemon run              # run until interrupted
llmc-rag-daemon tick             # single scheduler tick then exit
llmc-rag-daemon config --json    # show effective config
llmc-rag-daemon doctor           # basic health checks
```

Defaults:

- Config file: `~/.llmc/rag-daemon.yml` (overridable via `LLMC_RAG_DAEMON_CONFIG` or `--config`).
- Sensible defaults for tick interval, concurrency, state store, log directory, and control directory.

Error handling:

- Missing config → clear `error: Daemon config not found ...` plus a hint about where to create it.
- Missing or unwritable state/log/control paths → surfaced via `doctor` with `[ERROR]` lines and non-zero exit.

## llmc-rag-service – “Real Human” UX

Backed by `tools.rag.service` via `scripts/llmc-rag-service`.

High-level management CLI that wraps repo registration and the background service loop.

```bash
llmc-rag-service                        # tree-style help
llmc-rag-service register /home/you/src/llmc
llmc-rag-service start --interval 300   # foreground loop
llmc-rag-service start --interval 300 --daemon
llmc-rag-service status
llmc-rag-service stop
llmc-rag-service clear-failures --repo /home/you/src/llmc
```

Responsibilities:

- Tracks managed repos and service state in `~/.llmc/rag-service.json`.
- Orchestrates per-repo refresh cycles using the RAG runner/config modules.
- Records and clears failures via `~/.llmc/rag-failures.db`.

Error handling and UX:

- `start` when already running → prints `Service already running (PID …)` instead of crashing.
- `status` with no running service → clearly shows `stopped` and any tracked repos.
- Missed or invalid arguments → short error plus usage/help, never raw tracebacks.
