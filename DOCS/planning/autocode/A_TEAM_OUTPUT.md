# A-Team Output: Phase 1 - Move Existing Docs

**Date:** 2025-12-16
**Phase:** 1 - Move Existing Docs
**Author:** A-Team (Documentation Drafter)

---

## Executive Summary

Successfully migrated existing documentation from the flat `DOCS/` structure into the new Diátaxis-based hierarchy (`user-guide/`, `architecture/`, `operations/`, etc.). Verified and updated internal links within the User Guide to reflect new file paths.

---

## Actions Taken

### 1. Requirements Definition
Created `DOCS/planning/autocode/REQUIREMENTS.md` detailing the migration plan, acceptance criteria, and source/target mappings.

### 2. File Migration
Executed `git mv` to restructure the documentation:

- **User Guide:**
  - `CLI_REFERENCE.md` → `user-guide/cli-reference.md`
  - `LLMC_USER_GUIDE.md` → `user-guide/overview.md`
  - `Docgen_User_Guide.md` → `user-guide/docgen.md`
  - `Remote_LLM_Providers_Usage.md` → `user-guide/enrichment/providers.md`
  - `CONFIG_TUI.md` → `user-guide/tui/dashboard.md`
  - `TE_ANALYTICS.md` → `user-guide/tool-envelope.md`
  - `RUTA_User_Guide.md` → `user-guide/ruta.md`

- **Operations & Architecture:**
  - `RAG_Doctor_User_Guide.md` → `operations/troubleshooting.md`
  - `ROUTING.md` → `architecture/routing.md`
  - `HLD_TUI_AGENT.md` → `architecture/tui-agent.md`
  - `MCP_DESIGN_DECISIONS.md` → `architecture/mcp-decisions.md`
  - `RAG_Enrichment_Hardening.md` → `architecture/enrichment-hardening.md`

- **Development & Planning:**
  - `TUI_STYLE_GUIDE.md` → `development/tui-style.md`
  - `ROADMAP.md` → `planning/roadmap.md`
  - `ROADMAP_COMPLETED.md` → `planning/completed.md`
  - `SDD_Event_Driven_RAG_Service.md` → `planning/sdd/SDD_Event_Driven_RAG_Service.md`

- **Legacy/Archive:**
  - `CLI_UX_Progressive_Disclosure.md` → `legacy/`
  - `MIGRATION_UNIFIED_CLI.md` → `legacy/`
  - `notes.md` → `legacy/`
  - `DOCUMENTATION_PLAN.md` → `planning/archive/`

### 3. Link Updates
Updated relative links in `DOCS/user-guide/*.md` using `sed` to fix breakage caused by moving files into subdirectories:
- Adjusted `CLI_REFERENCE.md` references.
- Adjusted `ROADMAP.md` references to `../planning/roadmap.md`.
- Adjusted `SDD` references to `../legacy/...`.
- Adjusted `Remote_LLM_Providers_Usage.md` references.

---

## Terminology Decisions

- **Diátaxis:** Adopted the 4-quadrant structure (Tutorials, How-To, Reference, Explanation).
- **Naming:** Renamed `LLMC_USER_GUIDE.md` to `overview.md` as it serves as the general entry point for the User Guide until further split.
- **Legacy:** Moved superseded design docs to `legacy/` or `planning/archive/`.

---

## Outstanding Items / Blockers

- **Index Updates:** `DOCS/index.md` was found to be pre-generated (likely in Phase 0) and generally aligned, but individual sub-index files (e.g., `DOCS/architecture/index.md`) may need content updates in future phases (Phase 3c).
- **Deep Linking:** Some specific section links (anchors) might be broken if the target file structure changed significantly, though file-level links are addressed.

---
SUMMARY: Migrated 20+ files to Diátaxis structure, updated user-guide links, created requirements.
