# Implementation Plan: Productization Sprint 1 (Unified CLI)

**Status:** Completed
**Branch:** feature/productization
**SDD:** DOCS/planning/SDD_Unified_CLI_v2.md

---

## Phase 0: Foundation (Completed)
**Goal:** Create minimal scaffolding with zero risk.

- [x] `llmc/core.py` - Config finder, version info
- [x] `llmc/main.py` - Typer app with `--version` and `--help`
- [x] `llmc/commands/__init__.py` - Empty package
- [x] `pyproject.toml` update - Add `llmc = "llmc.main:app"` and deps
- [x] Install test - `pip install -e . && llmc --version`

## Phase 1: Core Commands (Completed)
**Goal:** Add basic, self-contained commands.

- [x] `llmc/commands/init.py` - Bootstrap `.llmc/` workspace
- [x] `llmc version` - Show version, paths, config status (Implemented via --version flag)

## Phase 2: RAG Command Delegation (Completed)
**Goal:** Expose core RAG commands.

- [x] `llmc/commands/rag.py` - RAG command module
  - [x] `index`
  - [x] `search`
  - [x] `inspect`
  - [x] `plan`
  - [x] `stats`
  - [x] `doctor`

## Phase 3: TUI Integration (Completed)
**Goal:** Launch TUI from unified CLI.

- [x] `llmc/commands/tui.py` - TUI launcher
  - [x] `tui`
  - [x] `monitor` (alias)
