# HLD: Unified CLI & Productization ("Defuckingscriptify")

## 1. Goal
To transform LLMC from a loose collection of scripts into a cohesive, installable product with a single entry point (`llmc`). This focuses on **User Experience (UX)**, **Speed** (eliminating interpreter startup latency), and **Maintainability** (centralized config).

## 2. Problem Statement
*   **Fragmentation:** Functionality is split across `rag_plan_helper.sh`, `qwen_enrich_batch.py`, `rag_refresh.sh`, and python modules.
*   **Latency:** Chained bash scripts that call Python incur repeated interpreter startup costs (100ms+ per call), making the tool feel sluggish.
*   **Config Hell:** Configuration is scattered across environment variables (`.envrc`) and argument flags.
*   **UX:** No unified "Dashboard" or status view; users grep logs to see what's happening.

## 3. Proposed Architecture

### 3.1 The Stack
*   **CLI Framework:** `Typer` (Python) - Type-safe, fast, auto-documented.
*   **UI Library:** `Rich` (Python) - For the "Cyberpunk TUI" aesthetic (tables, spinners, dashboards).
*   **Config:** `TOML` (`llmc.toml`) - Standardized configuration file.

### 3.2 Layered Design
```mermaid
[ User ] -> [ llmc CLI (Typer) ] -> [ Controller Layer ] -> [ Core Library (tools.*) ]
                                          |
                                          v
                                    [ Config Loader ]
```
*   **CLI Layer:** parsing args, printing `Rich` UI. **No business logic.**
*   **Controller Layer:** Orchestrates calls to the Core Library. Handles `llmc.toml` loading, error mapping (Exception -> User Message).
*   **Core Library:** The existing `tools.rag.*` modules. Refactored slightly to expose cleaner Python APIs if needed.

## 4. Command Hierarchy

The `llmc` binary will support these primary commands:

### 4.1 Lifecycle
*   `llmc init`: Scaffolds `.llmc/`, creates default `llmc.toml`.
*   `llmc doctor`: Checks dependencies (git, sqlite, disk space) and configuration health.

### 4.2 Daemon Management
*   `llmc start`: Starts the RAG daemon (replacing `rag_service.py` direct calls).
*   `llmc stop`: Stops the daemon (sends signal).
*   `llmc restart`: Convenience.

### 4.3 Interactive / TUI
*   `llmc monitor`: The **Live Dashboard**.
    *   Connects to SQLite (read-only) to poll status.
    *   Tails log files.
    *   Shows: Queue size, Token usage, Index freshness, Active Agents.
*   `llmc status`: A one-shot print of the dashboard stats (for scripts/CI).

### 4.4 Tools (The "API")
*   `llmc search "query"`: Wraps `tool_rag_search`. Pretty-prints results.
*   `llmc ask "question"`: (Future) RAG-augmented chat.
*   `llmc enrich`: Manually triggers the enrichment pipeline (replacing `qwen_enrich_batch.py`).

## 5. Configuration (`llmc.toml`)

Replace scattered env vars with a structured file:

```toml
[project]
name = "my-repo"
root = "."

[rag]
enable_enrichment = true
index_path = ".llmc/rag/index_v2.db"

[llm]
provider = "openai" # or "ollama", "anthropic"
enrichment_model = "gpt-4o-mini"
# host/key resolved from env vars or secure store

[ui]
theme = "cyberpunk"
verbose = false
```

## 6. Implementation Strategy

### Phase 1: The Skeleton (Day 1)
*   Setup `llmc` package structure.
*   Implement `llmc --help` and `llmc init`.
*   Implement `ConfigLoader`.

### Phase 2: The Migration (Day 2-3)
*   **Port Search:** Wire `llmc search` to `tools.rag_nav.tool_handlers`.
*   **Port Daemon:** Wire `llmc start` to `tools.rag_daemon.service`.
*   **Port Enrichment:** Refactor `qwen_enrich_batch.py` into a callable library function and wire to `llmc enrich`.

### Phase 3: The Polish (Day 4)
*   Implement `llmc monitor` with real SQLite hooks.
*   Add "Cyberpunk" styling.
*   Delete `.sh` scripts.

## 7. Success Metrics
*   **Zero Bash:** No `.sh` files required for normal operation.
*   **Speed:** `llmc search` responds <500ms (hot cache) vs multi-second script chains.
*   **Install:** `pip install .` works in a fresh venv.

## 8. Risks
*   **Dependency Hell:** `rich` and `typer` must be managed.
*   **Migration Breakage:** Existing "Ruthless" tests rely on scripts. We must update tests to call the `llmc` entry point or Python API directly.
