# SDD: Productization & Unified CLI (Roadmap 2.1)

**Author:** Ren (Gemini 3.0)
**Date:** 2025-12-02
**Status:** Draft

## 1. Context
LLMC currently operates as a collection of loose scripts (`scripts/*.py`, `tools/rag/cli.py`, etc.). While powerful, this "script soup" makes installation, discovery, and usage difficult for new users. Roadmap item 2.1 "Productization and packaging" aims to unify these into a single, coherent `llmc` CLI command.

## 2. Goals
*   **Unified Entrypoint:** A single `llmc` command that manages the entire lifecycle (init, index, query, service).
*   **Standard Install:** `pip install -e .` should result in a working `llmc` command on the path.
*   **Performance:** Reduce the `bash -> python` wrapper overhead by calling Python directly.
*   **Cleanliness:** Encapsulate the "messy" implementation details behind a clean CLI interface.

## 3. User Experience (CLI Design)

The `llmc` command will use `typer` (following the pattern in `llmc/cli.py`) to provide subcommands.

```bash
llmc [GLOBAL_FLAGS] COMMAND [ARGS]
```

### 3.1 Core Commands
| Command | Description | Current Equivalent |
| :--- | :--- | :--- |
| `init` | Bootstrap a new repo with `.llmc/` config. | Manual setup |
| `index` | Run the indexing/enrichment pipeline. | `scripts/rag_refresh.sh` / `tools/rag/cli.py` |
| `search` | Query the RAG index. | `tools/rag/cli.py search` |
| `inspect` | Deep dive into a file or symbol. | `tools/rag/cli.py inspect` |
| `service` | Manage the background daemon. | `scripts/llmc-rag-service` |
| `route` | Run the routing evaluation (optional/dev). | `scripts/router.py` |
| `tui` | Launch the interactive dashboard. | `llmc/tui/app.py` (or existing demo) |

### 3.2 Example Usage
```bash
# Setup
llmc init

# Indexing
llmc index --verbose

# Searching
llmc search "how does the router work?"

# Daemon Management
llmc service start
llmc service status
llmc service logs
```

## 4. Technical Design

### 4.1 Architecture
The existing `llmc/cli.py` (currently a TUI demo) will be refactored to become the main entry point.

**Directory Structure:**
```text
llmc/
├── cli.py          # Main Typer app entry point
├── commands/       # New module for command implementations
│   ├── __init__.py
│   ├── init.py     # Implementation of `llmc init`
│   ├── index.py    # Implementation of `llmc index` (wraps tools.rag)
│   ├── query.py    # Implementation of search/inspect
│   └── service.py  # Implementation of daemon control
```

### 4.2 Integration Points
*   **RAG Operations:** The `index` and `query` commands will import directly from `tools.rag.cli` and `tools.rag.core` to avoid subprocess overhead.
*   **Daemon:** `llmc service` will likely still need to manage a subprocess (for the daemon itself), but the *control* logic (start/stop/check pid) will be Python.
*   **TUI:** `llmc tui` will import the textual app from `llmc.tui.app` and run it.

### 4.3 Configuration
*   The CLI will check for `llmc.toml` in the current directory (or parents).
*   If not found, `llmc init` will generate a default one.

## 5. Migration Plan
1.  **Scaffold:** Create `llmc/commands/` and move `llmc/cli.py` logic to proper subcommands.
2.  **Port RAG:** Refactor `tools/rag/cli.py` functions to be callable libraries, not just CLI entry points.
3.  **Port Daemon:** Implement `llmc service` using `subprocess` or `daemon` libraries to replace `scripts/llmc-rag-service` logic.
4.  **Entrypoint:** Update `pyproject.toml` to expose `llmc = llmc.cli:app`.
5.  **Cleanup:** Mark old scripts as deprecated or replace them with shims that call `llmc ...`.

## 6. Testing Strategy
*   **Install Test:** Verify `pip install .` creates the `llmc` command.
*   **Smoke Test:**
    *   `llmc --help` returns exit code 0.
    *   `llmc init` creates `.llmc/` in a temp dir.
    *   `llmc search` returns "Index not found" (graceful fail) in empty dir.
*   **Unit Tests:** Test each subcommand function in isolation using `typer.testing.CliRunner`.

## 7. Risks & Unknowns
*   **Path Handling:** Ensuring the CLI works correctly regardless of where it is invoked (CWD vs Repo Root).
*   **Environment:** The `llmc` command must run in the same environment as the installed package.
