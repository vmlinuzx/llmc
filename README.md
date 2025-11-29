THE LARGE LANGUAGE MODEL COMPRESSOR

**Current Release:** v0.5.5 "Modular Mojo"

For the impatient quick start:

```bash
pip install -e ".[rag]"
llmc-rag-repo add /path/to/repo
llmc-rag-service register /path/to/repo
llmc-rag-service start --interval 300 --daemon
```

### What's New in v0.6.0 "Modular Mojo"
- **Modular Embeddings:** You can now define multiple embedding **profiles** (e.g., `code` vs. `docs`) using different providers (Ollama, SentenceTransformers, Hash) in `llmc.toml`.
- **Hardened CLI:** Critical bug fixes for `llmc-rag` and `llmc-rag-repo snapshot`.
- **Better Telemetry:** Unified SQLite-backed telemetry for the Tool Envelope.
- **Quality:** Massive codebase cleanup and new live integration tests.


Originally created by David Carroll, the worst paragliding pilot in the TX Panhandle 8 years running when he crashed out after burning through his weekly limits on his subscriptions, and decided to find a way to lower usage. This is it.

This project was originally just me wanting to learn how to set a RAG up because I kept getting crushed by token usage in Claude when using Desktop Commander. Then I thought.. I can do better, so I started reading research papers, and things just got out of hand. The system is built to create massive token, context, and inference savings while working with an LLM in a repo. Right now it is geared toward a python repo, but works with some limitations for just about anything. You should see between 70 and 95 percent reduction in token usage in a long session by using the LLMC.  I can feel when I'm not using it because LLM's work much slower, context poison themselves more, context window fills much faster, etc.


Brief what this repo does: A small set of CLIs and services that keep the users different project repos indexed, enriched, and queryable via RAG designed to utilize local smaller agents to drive down LLM usage costs, and make big LLM's "smarter".


Capabilities:
- Core RAG in sqlite engine: Local, file based RAG index that keeps a repo's code and docs searchable without calling an LLM.
    - Index: Scans the repo, slices files into logical spans (functions, classes, top level blocks), and stores text plus metadata in a sqlite database with full text search tables.
    - Sync: Keeps the index up to date by applying incremental changes from git diffs or explicit file lists instead of re indexing everything.
    - Embeddings: Turns spans into vector embeddings using a configured embedding backend, caches them in sqlite, and skips recompute when the source text has not changed.
    - Enrichment (LLM call): Calls the configured enrichment backends to generate summaries, tags, and other metadata that make search and ranking smarter.
    - Planner/context trimmer: Takes a query plus candidate spans and packs the best ones into a fixed context budget so prompts stay small and relevant.
    - Search CLI: Provides command line commands to run semantic and keyword search, where used, lineage search, stats, and benchmarks directly against the local index.
    - Analytics and benchmarks: Offers simple checks so you can sanity check embedding quality, ranking behavior, and index health.

- Schema graph and GraphRAG: Builds and uses a code level graph so LLMC can see how things are wired together.
    - Schema extraction: Parses code into entities (functions, classes, modules, etc.), captures relationships like calls, imports, extends, etc., then writes a graph manifest file under .llmc.
    - Graph store: Keeps an in memory adjacency map so tools can walk neighbors, limit hops, and filter edges quickly.
    - Graph aware query enrichment: Detects when a query is about a symbol or module, finds the relevant entities, and pulls in their graph neighbors as extra context for RAG.
    - Nav metadata: Tracks graph version, last built commit, and freshness stamps so other tools can see if the graph is fresh enough to trust.

- RAG Nav and freshness routing: High level tools that sit in front of RAG and decide when and how to use the index.
    - Freshness envelopes: Tracks how fresh slices are compared to the current repo, and refuses to return stale slices instead of lying to LLMs.
    - Fallback logic: When RAG is too stale or missing, recommends falling back to live repo reads or direct file inspection instead of pretending everything is fine.
    - Status reporting: Exposes per repo freshness, coverage, and error counts so you can see when something is broken or drifting.
    - Graph aware RAG tools: Implements search, where used, and lineage with both index and graph knowledge so answers include both content and structure.

- Daemon and service layer: Background workers that keep things fresh without you having to babysit.
    - llmc-rag-service: Human facing CLI for registering repos, starting/stopping refresh loops, and checking status from the shell.
    - llmc-rag-daemon: Lower level scheduler loop that walks registered repos and runs index/embed/enrich work according to config.
    - Failure store: Keeps track of failed jobs in a sqlite db so you can inspect, debug, and clear them instead of silently dropping errors.
    - Tick and doctor commands: Let you run one off checks or a single scheduler tick to debug without committing to a full daemon loop.

- Repo registry and workspace safety: Helps LLMC know which repos exist and where their workspaces live.
    - Repo registry: Stores a list of repos, their normalized paths, and basic metadata in a small yaml file under ~/.llmc.
    - Workspace helpers: Uses a workspace helper module to map repos to .llmc directories safely, and to avoid unsafe path traversal.
    - Snapshot and clean helpers: Offers commands to snapshot and clean workspaces, with force flags and clear error codes to avoid footguns.
    - Doctor paths: Shows what paths are allowed or blocked for a workspace, making it easier to debug weird path issues.

- Desktop Commander and MCP integration: Lets other tools treat LLMC as a safe, documented set of RAG and graph tools.
    - Tool manifest: Documents tools like search, where used, lineage, and status so agents know how to call them and what to expect back.
    - JSON envelopes: Returns structured JSON with spans, paths, scores, and freshness flags instead of dumping big blobs of text.
    - Safety constraints: Follows explicit policies about what paths can be read, what repos can be touched, and what side effects are allowed.
    - Agent friendly defaults: Designs tools to be composable, so agents can chain a few calls to explore code, plan refactors, or answer questions.

- Router, LLM chains, and enrichment control: The layer that decides which model to use for which job.
    - Model registry: Lets you configure multiple model backends (local Qwen, remote MiniMax, etc.) with URLs, timeouts, and options.
    - Enrichment chains: Defines chains of models to use for enrichment, including fallback chains when one model fails or times out.
    - Latin 1 safety: Supports enforcing latin 1 safe enrichment so weird unicode or binary junk does not poison the index.
    - Cost awareness: Encourages using small, cheap models for most work and reserving bigger, slower models for special or complex chains.

- TUI and console UX: A second monitor experience for watching LLMC do its thing.
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
    - Quality scripts: Small scripts that exercise critical paths like freshness envelopes and core search paths from the shell.

- Misc utilities and experiments: One off tools that make it easier to use or inspect the system.
    - Context zip packaging: Bundles the important parts of a repo's .llmc directory plus relevant config and test artifacts into a zip for remote debugging or pairing with another tool.
    - Log cleaning and compression: Cleans or compresses old logs so LLMC can run for long periods without filling disks.
    - Prototype web server: Early experiments for exposing LLMC via HTTP; currently considered experimental and not part of the main product surface.

Limitations:

- Graph is currently Python first: The graph extraction and schema logic targets Python repos; other languages have to fall back to more naive parsing until full walkers exist.
- Index freshness is bounded by your daemon: If your daemon or service is not running regularly, LLMC will fall back to being conservative and not returning stale slices.
- RAG Nav tools are opinionated: The system prefers "no answer" to "bad answer", which can feel strict if you are used to LLMs happily hallucinating from junk input.
- Some config lives in code: Not every knob is exposed in llmc.toml or config files yet; some advanced settings still require code changes.
- Prototype features are present: Some old experiments (like the web server) still live in the repo but are not wired into the main CLIs by default.
- There is a little logic to not enrich the same chunk, but the enrichment logic can still be wasteful across a number of runs.  I have the solution for that, but haven't implemented it yet.

