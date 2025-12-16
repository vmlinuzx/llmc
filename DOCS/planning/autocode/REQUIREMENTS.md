# REQUIREMENTS: Phase 1 - Move Existing Docs

**SDD Source:** DOCS/planning/SDD_Documentation_Architecture_2.0.md → Phase 1
**Target Document:** DOCS/ (Restructuring)
**Audience:** A-Team (Executor), B-Team (Verifier)

---

## Objective

Move existing documentation files from the flat `DOCS/` structure into the new Diátaxis-based hierarchy (`user-guide/`, `architecture/`, `operations/`, etc.) to improve discoverability and organization. This phase focuses on filesystem operations and link updates, not rewriting content.

---

## Acceptance Criteria

### AC-1: User Guide Migration

**Location:** `DOCS/user-guide/`

The following files must be moved to their new locations:
- `CLI_REFERENCE.md` → `user-guide/cli-reference.md`
- `LLMC_USER_GUIDE.md` → `user-guide/overview.md`
- `Docgen_User_Guide.md` → `user-guide/docgen.md`
- `Remote_LLM_Providers_Usage.md` → `user-guide/enrichment/providers.md`
- `CONFIG_TUI.md` → `user-guide/tui/dashboard.md`
- `TE_ANALYTICS.md` → `user-guide/tool-envelope.md`
- `RUTA_User_Guide.md` → `user-guide/ruta.md`

### AC-2: Operations & Architecture Migration

**Location:** `DOCS/operations/` and `DOCS/architecture/`

The following files must be moved/merged:
- `RAG_Doctor_User_Guide.md` → `operations/troubleshooting.md`
- `ROUTING.md` → `architecture/routing.md`
- `HLD_TUI_AGENT.md` → `architecture/tui-agent.md`
- `MCP_DESIGN_DECISIONS.md` → `architecture/mcp-decisions.md` (Note: SDD says security-model.md, Plan says mcp-decisions.md. Using mcp-decisions.md for now as distinct file, merge happens later).
- `RAG_Enrichment_Hardening.md` → `architecture/enrichment-hardening.md`

### AC-3: Development & Planning Migration

**Location:** `DOCS/development/` and `DOCS/planning/`

The following files must be moved:
- `TUI_STYLE_GUIDE.md` → `development/tui-style.md`
- `ROADMAP.md` → `planning/roadmap.md`
- `ROADMAP_COMPLETED.md` → `planning/completed.md`
- `SDD_Event_Driven_RAG_Service.md` → `planning/sdd/SDD_Event_Driven_RAG_Service.md`
- Any other `DOCS/planning/SDD_*.md` → `planning/sdd/`

### AC-4: Archive (Legacy)

**Location:** `DOCS/legacy/`

The following files must be moved to legacy:
- `CLI_UX_Progressive_Disclosure.md`
- `MIGRATION_UNIFIED_CLI.md`
- `notes.md`
- `DOCUMENTATION_PLAN.md` → `planning/archive/`

### AC-5: Link Integrity

- All relative links in moved files (e.g., `[Link](../other.md)`) must be updated to reflect the new depth.
- `DOCS/index.md` must link to the new locations (or section indexes).

---

## Style Requirements

- **Command:** Use `git mv` to preserve history.
- **Paths:** Relative paths in links must be correct.
- **Content:** Do not rewrite content body, only links.

---

## Out of Scope

- ❌ Writing new content for placeholders.
- ❌ Splitting `LLMC_USER_GUIDE.md` (deferred to Phase 2).
- ❌ Merging content (unless simple rename).

---

## Verification

B-Team must verify:
1. `ls DOCS/*.md` shows only `index.md`.
2. All target files exist in new locations.
3. `grep -r "](\.\./" DOCS/` checks for broken relative links (excluding planning archives if applicable).

---

**END OF REQUIREMENTS**
