# LLMC User Guide

Welcome to the "how do I actually use this thing" guide for the Large Language Model Commander (LLMC).

- The **README** tells the story and what the system is.
- This **User Guide** is the exhaustive "how do I install it, wire it, and actually drive it" manual.

If you are just kicking the tires, start with the **Quick Start** section. If you are integrating this into an agent stack or Desktop Commander, you probably want the sections on **Concepts**, **CLI surfaces**, and **Workflows**.

---

## 1. What LLMC Is (and Is Not)

LLMC is a local-first RAG and tooling stack for code and docs. In plain terms:

- It keeps your repos indexed, enriched, and searchable in a local SQLite database.
- It uses small, cheap models first, and only calls big, expensive models when it really has to.
- It prefers **no answer** over a **wrong answer from stale context**.
- It is built to be used by other tools and agents (Desktop Commander, MCP-style bridges, etc.).

LLMC is **not**:

- A hosted SaaS.
- A permanent memory or journaling system.
- A one-click refactor bot.
- A general-purpose chat front end.

Think of it as the "local brain" that sits next to your repos and feeds the LLM only what it actually needs.

---

## 2. Core Concepts and Architecture

At a high level, LLMC is made of these layers:

1. **Core RAG engine (SQLite)**  
   - Indexes files and slices them into spans (functions, classes, top-level blocks).
   - Stores full-text data and vector embeddings.
   - Provides search and retrieval for agents and tools.

2. **Schema graph and GraphRAG**  
   - Builds a graph of entities (functions, classes, modules) and relationships (calls, imports, extends).
   - Lets you answer questions about "who calls what", "where is this defined", and "what depends on this".

3. **RAG Nav and freshness routing**  
   - Tracks how fresh the index and graph are compared to the repo.
   - Decides whether to trust RAG results or fall back to the live filesystem.
   - Refuses to return slices that are out of date. It will prefer "no RAG hits" over lying.

4. **Daemon and service layer**  
   - Keeps registered repos fresh in the background.
   - Schedules indexing, embedding, and enrichment work safely.

5. **Repo registry and workspace safety**  
   - Manages which repos are registered.
   - Manages their `.llmc` workspaces and enforces strict path safety.

6. **Router and enrichment chains**  
   - Encodes which models are available (local Qwen, remote MiniMax, etc.).
   - Decides which one to use for enrichment and other LLM calls.
   - Enforces options like `enforce_latin1_enrichment` so junk inputs do not poison the DB.

7. **TUI and console UX**  
   - Textual-based TUI that lives nicely on a second monitor.
   - Rich-based console dashboard for lighter-weight monitoring.

8. **Desktop Commander / agent integration**  
   - Exposes the RAG and graph tools as safe, documented tools (search, where-used, lineage, etc.).

You can use as much or as little of this stack as you want. The minimal setup is: register a repo, run the service, and let agents call the RAG tools.

---

## 3. Installation and Setup

### 3.1. Prerequisites

- Python 3.12 (or compatible)
- git
- A Unix-like environment (tested on Linux)
- Optional but recommended: virtualenv

Create and activate a virtualenv, then install LLMC in editable mode with RAG extras:

```bash
cd ~/src/llmc
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[rag]"
```

To make the CLIs feel like real commands, ensure your installation method exposes `llmc-cli` or add the local binary path to your shell.

After that, commands like `llmc-cli` should be available from any shell.

### 3.2. First-time Configuration

LLMC uses a mix of:

- A global config directory under `~/.llmc/` for things like:
  - Repo registry (`repos.yml`)
  - Daemon config (`rag-daemon.yml`)
  - Service state (`rag-service.json`)
  - Failure store (`rag-failures.db`)
- Per-repo workspaces under `REPO/.llmc/` for:
  - RAG indexes (SQLite DBs)
  - Graph manifests
  - Internal metadata

You will usually touch:

- `~/.llmc/rag-daemon.yml` if you want to tweak how the daemon runs.
- `llmc.toml` in your repo if you want to control embeddings, enrichment chains, router behavior, and logging.

If those files do not exist, the CLIs will try to use sensible defaults and guide you with error messages when something is missing.

---

## 4. Quick Start: The Minimal Happy Path

This is the simplest "I want this working in one repo" flow.

### Step 1: Register a repo

Tell LLMC that a repo exists and should have a workspace.

```bash
llmc-cli repo register /home/you/src/your-repo
```

You can list and inspect registered repos:

```bash
llmc-cli service repo list
llmc-cli debug inspect /home/you/src/your-repo
```

This sets up `.llmc/rag` under your repo and writes to the global registry.

### Step 2: Start the service

Use the high-level service wrapper to kick off background refresh cycles:

```bash
llmc-cli service repo add /home/you/src/your-repo
llmc-cli service start --interval 300 --daemon
```

- `repo add` tells the service which repos to manage.
- `start` launches the refresh loop (foreground by default; add `--daemon` to background it).

Check status:

```bash
llmc-cli service status
```

You should see whether the service is running and which repos are managed.

### Step 3: Let it index and enrich

Give it a bit of time for the first run to:

- Index the repo into `.rag/index_v2.db`.
- Embed spans.
- Run enrichment jobs.

You can monitor progress via logs, the daemon, or the TUI (see later sections).

### Step 4: Use it from tools or agents

Once the index is built, you can:

- Use the RAG CLI directly for search.
- Let the TUI handle queries.
- Wire it into Desktop Commander or another agent layer using the documented tools (search, where-used, lineage, etc.).

---

## 5. Main Command-line Surfaces

There are two primary "front door" command groups:

- `llmc-cli repo` - manage which repos are registered for RAG.
- `llmc-cli service` - high-level service wrapper and daemon.

The new unified `llmc-cli` CLI provides subcommands that replace the older, separate scripts (like `llmc-rag-repo` and `llmc-rag-service`).

### 5.1. `llmc-cli repo` - Repo Registry

The `llmc-cli repo` command group manages the global repo registry (`~/.llmc/repos.yml`) and per-repo `.llmc` workspaces.

Common commands:

```bash
llmc-cli repo --help               # See all repo commands
llmc-cli repo register /home/you/src/llmc
```

Key behaviors:

- Normalizes paths and creates `.llmc` workspaces as needed.
- Writes and reads `~/.llmc/repos.yml`.
- Prints short, friendly errors on bad input instead of dumping tracebacks.

### 5.2. `llmc-cli service` - Daemon and Service Management

The `llmc-cli service` command group runs the scheduler loop that keeps registered repos fresh, replacing the legacy `llmc-rag-daemon` and `llmc-rag-service` scripts.

Common commands:

```bash
llmc-cli service --help              # See all service commands
llmc-cli service start               # Run in foreground
llmc-cli service start --daemon      # Run in background
llmc-cli service status              # Check health and status
llmc-cli service logs -f             # Tail logs
llmc-cli service stop                # Stop the background service
```

This unified command handles:
- Tracking managed repos and service state in `~/.llmc/rag-service.json`.
- Orchestrating per-repo refresh cycles using the `llmc.rag` modules.
- Recording failures in `~/.llmc/rag-failures.db`.

Configuration is managed in `llmc.toml`, and `llmc-cli debug doctor` provides comprehensive health checks.

Error handling and UX:

- `start` when already running: prints `Service already running (PID ...)` instead of crashing.
- `status` when stopped: clearly shows `stopped` and any tracked repos.
- Bad arguments: short error plus usage; no raw tracebacks.

---

## 6. Path Safety and Workspace Helpers

LLMC includes diagnostic and recovery tools under the `llmc-cli debug` and `llmc-cli repo` command groups.

### 6.1. `doctor`, `export`, and `repo clean`

Quick examples:

```bash
llmc-cli debug doctor --json
llmc-cli debug export --output /tmp/backup.tar.gz
llmc-cli repo clean --force --json
```

- `llmc-cli debug doctor`: Checks workspace safety, configuration, and index health.
- `llmc-cli debug export`: Creates a snapshot of a workspace for backup or debugging.
- `llmc-cli repo clean`: Wipes workspace contents to rebuild indexes from scratch. Destructive operations require `--force`.

---

## 7. Core RAG Operations

Most of the heavy lifting lives under the `llmc.rag` package. You will usually access it via the `llmc-cli` CLI. The important concepts are:

- **Index**: Scans a repo, slices files into spans, and stores them.
- **Sync**: Applies incremental changes from git or explicit file lists.
- **Embeddings**: Computes and caches vector embeddings.
- **Enrichment**: Calls configured LLM chains to add summaries and metadata.
- **Search**: Queries the local index using a mix of keyword and vector search.

A typical manual workflow uses the `debug` and `analytics` commands:

- **Initial index**: `llmc-cli debug index`
- **Sync after local changes**: `llmc-cli debug sync --since HEAD~1`
- **Embed spans**: `llmc-cli debug embed`
- **Enrich spans**: `llmc-cli debug enrich`
- **Run a query**: `llmc-cli analytics search "how does X call Y"`

The pattern is always: index, sync, embed, enrich, then search. The `llmc-cli service` command automates this loop.

### 7.1. Normalized Scoring

LLMC provides two types of scores in search results:

1.  **Normalized Score** (e.g., `[ 95.0]`): A 0-100 score representing the absolute similarity of the result to your query. 100 is a perfect match. This is comparable across different queries.
2.  **Ranking Score** (e.g., `(0.945)`): The internal score used to sort results. This may include boosting, fusion weights, and relative scaling. It is useful for debugging ranking logic but is not strictly comparable across queries.

CLIs and TUIs display the Normalized Score prominently as it is the best indicator of "how good is this hit?".

---

## 8. RAG Nav, Graph, and Freshness

RAG Nav is the layer that sits on top of core RAG and graph data and answers questions like:

- "Is the index fresh enough to trust?"
- "Where is this symbol defined?"
- "Who calls this function?"
- "Show me lineage around this module."

Typical commands (names may vary by version, but conceptually):

- `llmc-cli analytics graph` - rebuild the schema graph and mark it fresh.
- `llmc-cli analytics search` - metadata-driven search over files and entities.
- `llmc-cli analytics where-used` - show symbol usages.
- `llmc-cli analytics lineage` - show upstream/downstream relationships.

The **freshness envelope** behavior is important:

- LLMC tracks which slices match the current source state.
- If a slice is out of date (the file changed and the index has not caught up), that slice is dropped.
- If the index as a whole is too stale, LLMC will recommend "do not use RAG; fall back to the live repo" rather than returning stale context.

This is what keeps the system from silently lying to your LLM with old data.

---

## 9. TUI and Console Interfaces

If you like dashboards and second monitors, this is your section.

### 9.1. Textual TUI (`llmc-cli tui`)

The Textual-based TUI gives you:

- A monitor screen for repo / daemon / index health.
- A search screen for interactive RAG queries.
- A inspector screen for viewing symbols and their enriched context.
- A config screen that shows key settings from `llmc.toml` and RAG config.

Start it with something like:

```bash
llmc-cli tui
```

You can then:

- Switch screens using key bindings.
- Point it at a repo and see what LLMC thinks is going on.
- Use it as the "ops console" while agents and services run in the background.

### 9.2. Rich Console Dashboard

For lighter-weight usage, there is a console CLI (usually just `llmc-cli` with flags) that:

- Renders a multi-panel dashboard using Rich.
- Shows core metrics and status without the full TUI machinery.

This is handy for quick checks over SSH or in terminals where Textual is overkill.

---

## 10. Desktop Commander and Agents

LLMC is designed to be driven by agents, not just humans.

The integration points include:

- A documented tool manifest that describes:
  - Tool names and parameters.
  - Return types (usually JSON envelopes).
  - Safety and side effects.
- Wrapper scripts that plug CLIs into Desktop Commander and MCP bridges.

Typical tools include (names simplified):

- `rag_search` - run a query and return spans plus metadata.
- `rag_where_used` - find where a symbol is referenced.
- `rag_lineage` - get upstream/downstream relationships.
- `rag_status` - report freshness and index health for a repo.

Because the tools return structured JSON instead of plain text, agents can combine them, rank results, and decide what to show to the user or feed into an LLM.

---

## 11. Enrichment and Router Behavior

The enrichment system is production-ready for Python codebases:

- Ingests real repos into `.rag/index_v2.db`.
- Creates stable, searchable spans.
- Generates enrichment metadata (summaries, tags, usage snippets) via configured backends.
- Maintains referential integrity between `files`, `spans`, `embeddings`, and `enrichments`.

The router and enrichment chains let you:

- Define which models exist (local vs remote).
- Set timeouts and batch sizes.
- Control behavior like `enforce_latin1_enrichment`, `max_failures_per_span`, and token estimates.

Expected behavior:

- Local, cheap models (like a Qwen on your GPU) are used for routine enrichment.
- Remote or premium models are only used when needed or for specific chains.
- Bad or garbage text is either cleaned or skipped instead of corrupting the index.

---

## 12. Troubleshooting and Recovery

### 12.1. Checking paths and workspaces

If something feels off with a workspace, run the comprehensive health check:

```bash
llmc-cli debug doctor --json
```

This will tell you:

- Whether the workspace path is valid and configuration is sane.
- Which paths are allowed or blocked by security policy.
- The status of the RAG index and any potential corruption.

### 12.2. Wiping and rebuilding a workspace

If the index is badly out of date or corrupted, you can clean it and rebuild.

```bash
llmc-cli repo clean --force --json
```

Then re-run the normal workflows:

- `llmc-cli service start` for automated refresh.
- Or manual `llmc-cli debug index`, `embed`, `enrich` commands.

### 12.3. Checking daemon and service health

Use the `llmc-cli service` and `llmc-cli debug` commands:

```bash
llmc-cli service status
llmc-cli debug doctor
llmc-cli service logs -f
```

Look for:
- Service not running when you think it is.
- Errors in the logs.
- Stale or stuck jobs reported by `doctor`.

### 12.4. Logs

LLMC writes logs under a configured log directory (often under `.llmc` or a path set in `llmc.toml`).

Common tricks:

- Tail logs while running commands to see what is happening.
- Use provided log cleanup scripts to rotate and purge old logs.
- Never be afraid to snapshot and nuke a workspace; everything important is derived from the repo and config.

---

## 13. Limitations and Expectations

A few honest limitations to keep in mind:

- **Python-first graph**: graph and schema extraction are strongest for Python; other languages mostly use stubs until proper walkers exist.
- **Not a permanent history system**: LLMC focuses on "current repo state"; long-term journaling or conversation history is out of scope for now.
- **Some prototype pieces**: older experiments (like the early web server) exist but are not considered part of the main product surface.
- **Power user integration**: Desktop Commander and MCP integration assumes you are comfortable wiring agent configs and tool manifests.
- **Config gaps**: most things are configurable, but some knobs are still hard-coded or only documented in code and dev docs.

---

## 14. Suggested Next Steps

If you are reading this and wondering "what do I do right now?", here is the short version:

1. Install LLMC and add `scripts/` to your `PATH`.
2. Pick one repo you care about.
3. Run:
   - `llmc-cli repo register /path/to/repo`
   - `llmc-cli service repo add /path/to/repo`
   - `llmc-cli service start --interval 300 --daemon`
4. Let it run for a while.
5. Use the TUI or RAG search CLI to ask questions about that repo.

Once that feels good, you can:

- Add more repos.
- Tune `llmc.toml` and enrichment chains.
- Wire it into Desktop Commander and agents.
- Start deleting all the bespoke "let me grep the world" scripts you used to rely on.

LLMC is meant to sit quietly in the background, saving you tokens and making big LLMs act like they actually know your codebase.
