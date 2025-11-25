THE LARGE LANGUAGE MODEL COMPRESSOR

**Current Release:** v0.5.0 "Token Umami"

For the impatient quick start:  
    pip install -e ".[rag]"  
    llmc-rag-repo add /path/to/repo  
    llmc-rag-service register /path/to/repo  
    llmc-rag-service start --interval 300 --daemon  

Originally created by David Carroll, the worst paragliding pilot in the TX Panhandle 8 years running when he crashed out after burning through his weekly limits on his subscriptions, and decided to find a way to lower usage.  This is it.

This project was originally just me wanting to learn how to set a RAG up because I kept getting crushed by token usage in Claude when using Desktop Commander.  Then I thought.. I can do better, so I started reading research papers, and things just got out of hand.  The system is built to create massive token, context, and inference savings while working with an LLM in a repo.  Right now it's geared toward a python repo, but works with some limitations for just about anything.  You should see between 70 and 95 percent reduction in token usage in a long session by using the LLMC.  I can feel when I'm not using it because LLM's work much slower, context poison themselves more, context window fills much faster, etc.


Brief what this repo does: A small set of CLIs and services that keep the users different project repos indexed, enriched, and queryable via RAG designed to utilize local smaller agents to drive down LLM usage costs, and make big LLM's "smarter".


Capabilities:
- Core RAG in sqlite engine: Local, file based RAG index that keeps a repo's code and docs searchable without calling an LLM.
    - Index: Scans the repo, slices files into logical spans (functions, classes, top level blocks), and stores text plus metadata in a sqlite database with full text search tables.
    - Sync: Keeps the index up to date by applying incremental changes from git diffs or explicit file lists instead of re indexing everything.
    - Embeddings: Turns spans into vector embeddings using the configured model, caches them in sqlite, and skips recompute when the source text has not changed.
    - Enrichment (LLM call): Calls the configured enrichment chain on each span to attach summaries, usage notes, tags, and other metadata that make search and ranking smarter.
    - Planner/context trimmer: Takes a query plus candidate spans and packs the best mix of results into a fixed context budget so prompts stay small and relevant.
    - Search CLI: Provides command line commands to run semantic search, keyword search, stats, and benchmarks directly against the local index.
    - Analytics and benchmarks: Offers simple checks so you can sanity check embedding quality, ranking behavior, and index health.


- Schema graph and GraphRAG: Builds and uses a code level graph of entities and relationships to make RAG answers structure aware.
    - Schema extraction: Parses code into entities (functions, classes, methods, modules) and relations (calls, imports, extends, etc.), then writes a graph manifest file under .llmc.
    - Graph store: Keeps an in memory adjacency map so tools can walk neighbors, limit hops, and filter edges quickly.
    - Graph aware query enrichment: Detects when a query is about relationships, finds matching entities, and pulls in their graph neighbors as extra context for RAG.
    - Nav metadata: Tracks graph version, last built commit, and timestamps so other tools can see if the graph is fresh enough to trust.

- RAG Nav and freshness routing: High level tools that sit in front of RAG and decide when and how to use the index.
    - Index status: Returns detailed fresh or stale state for a repo, including last indexed commit, current git head, schema version, and any recent errors.
    - Graph builder CLI: Rebuilds the schema graph for a repo and updates status so UIs and agents know when it is safe to rely on it.
    - Search, where used, and lineage tools: Expose read only tools that do file level search, symbol usage lookup, and upstream or downstream lineage over the repo.
    - Context gateway: Compares index state to the live repo and emits a route decision telling callers whether to trust RAG, fall back to the live filesystem, or treat things as unknown.
    - Structured JSON envelopes: Returns machine friendly envelopes so agents and TUIs can consume search and lineage results without scraping text.
    - 300 second sleep on modified files reduces llm enrichment burden on files that are in-use.
    - Freshness envelope / stale slice filter: Ensures queries only use slices that match the current source state; out of date slices are dropped, and if the index is too stale the system prefers “no RAG results / use live repo” over returning wrong context.

- Daemon, workers, and service wrapper: Background process that keeps repos indexed and enriched on a schedule.
    - Job scheduler: Pulls jobs from a registry, runs workers, and enforces a cooldown period so the same repo is not hammered repeatedly.
    - Path safe API layer: Validates all paths up front and only operates inside configured repo roots and .llmc workspaces.
    - State store: Records the last status, timestamps, and durations for each job so tools can show what ran and what failed.
    - llmc rag service CLI: Friendly wrapper that starts, stops, and inspects the daemon, and tracks managed repos in a simple state file.
    - Failure tracking: Logs failures into a separate store and exposes commands to inspect or clear them.
    - Shell helpers: Provides small shell scripts for cron, tmux, and manual refresh runs around the core RAG CLI.

- Repo registration and workspace safety: Tools that know which repos are managed and where their .llmc workspaces live.
    - Repo registry CLI: Adds, removes, lists, and inspects registered repos, and initializes workspace folders when needed.
    - Workspace planning and validation: Ensures workspaces land under safe directories, not at unsafe locations like / or random mount points.
    - Safe filesystem helpers: Uses SafeFS style helpers so all path operations are canonicalized and constrained inside allowed roots.
    - Doctor, snapshot, and clean: Provides commands to diagnose path policy, take workspace snapshots, and wipe local RAG artifacts safely with explicit force flags.

- Desktop Commander and MCP integration: Wraps the RAG tools as safe, documented tools for agent frameworks.
    - Tool manifest: Documents each tool's parameters, return types, and side effects so agent frameworks can call them safely.
    - Wrapper scripts: Supplies small shell shims that plug the RAG CLIs into Desktop Commander and MCP bridges.
    - Schema aware retrieval: Lets agents ask questions like where is this defined or who calls this and get structured answers from RAG instead of raw grep.

- Router and multi model enrichment: Routing and batch enrichment logic that chooses between local and remote LLMs.
    - Router policy: Encodes simple tiers for local, mid tier, and premium models and chooses between them based on size, complexity, and risk of the request.
    - Token and complexity estimates: Uses cheap estimates to guess token count and code complexity before choosing a model tier.
    - Batch enrichment driver: Runs batch jobs against local models to enrich spans and coordinates retries and health checks.
    - llmc route CLI: Front door command that shows which model tier would be chosen for a given request and why.
    - Configurable enrichment chains: Reads chain definitions from llmc.toml, including endpoints, providers, timeouts, and safety flags such as enforce latin 1 enrichment.

- TUI and console UX: Text based user interfaces for watching and driving the system.
    - Textual TUI app: Full screen TUI that lives on a second monitor and shows live panels for system state.
    - Monitor screen: Shows repo status, graph stats, enrichment counts, and daemon health at a glance.
    - Search screen: Lets you type a query and run RAG Nav search, where used, and lineage and inspect structured results.
    - Inspector screen: Shows source for a symbol or file plus enriched metadata and graph neighbors in a split view.
    - Config screen: Displays key RAG and router config values so you can see which models and settings are active.
    - Rich console dashboard: Offers a lighter weight console dashboard for quick monitoring without the full TUI.

- Testing, QA, and dev helpers: Guardrails that keep this pile of scripts from quietly rotting.
    - Test plan docs: Written test plans that spell out what should be covered by unit and integration tests across the stack.
    - Python test suite: Unit and integration tests for core RAG logic, repo tooling, freshness, adapters, and scripts.
    - Dev utilities: Helpers for safe rewrites, quality baselines, and focused CLI checks when refactoring.
    - Quality scripts: Small scripts that exercise critical flows like freshness envelopes and core search paths from the shell.

- Misc utilities and experiments: One off tools that make it easier to use or inspect the system.
    - Context zip packaging: Bundles the important parts of a repo and its RAG artifacts into a zip for remote debugging or pairing with another tool.
    - Sync helpers: Example scripts for pushing context bundles or logs to external storage.
    - Log rotation and cleanup: Config and scripts for rotating and pruning log files so they do not fill disks.
    - Example configs: Sample daemon and registry configs that can be copied and tweaked for new environments.
    - An abandoned web server rag_server.py, I'll be working to improve the tui, because tui's are cooler than web servers.  


Limitations:
- This is not a "permanent history" system.  I dislike those due to context poisoning issues, however I may revisit making one.
- Python first graph extraction (python only support on graph right now): Schema and GraphRAG are strongest for Python; other languages mostly use stubs until language specific walkers are implemented.
- Prototype grade pieces: Some older parts like the early RAG web server are still experiments and not wired into the main stack.
- Real world text mess: Enrichment assumes mostly clean text and needs options like enforce latin 1 enrichment to cope with junk inputs.
- Narrow RAG Nav surface: RAG Nav focuses on metadata and file level search today; deeper symbol aware where used is still being expanded.
- Work in progress TUI: The TUI is functional but still under heavy iteration on layout and polish.
- Power user MCP integration: Desktop Commander tooling is usable but assumes someone who is comfortable wiring their own agent configs.
- There is a little logic to not enrich the same chunk, but the line numbers change everything after that line nubmer is re-enriched.  I have the solution for that, but haven't implemented it yet.
- MOSTLY configurable.  This was a personal tool


The three primary “front door” commands are:

- `llmc-rag-service` – high-level human-facing service wrapper, run this without options to display usage, this is probably what you want.
- `llmc-rag-repo` – manage which repos are registered for RAG.
- `llmc-rag-daemon` – low-level scheduler/worker loop to keep workspaces fresh.

All three live under `scripts/` and are thin Python shims into the `tools.*` modules.

## Enrichment System Status

The enrichment pipeline is production-ready for Python codebases:

- Ingests real repositories into a `.rag/index_v2.db` SQLite store.
- Creates stable, searchable code spans via `tools.rag.indexer` and `tools.rag.database`.
- Generates enrichment metadata (summaries, tags, evidence, usage snippets) using the configured backends.
- Maintains referential integrity between `files`, `spans`, `embeddings`, and `enrichments`.
- Exposes a queryable enrichment surface via `tools.rag.database` and `tools.rag.db_fts` for downstream tools and agents.

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
