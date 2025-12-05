# HLD Research: Automated Repository Onboarding

**Status:** Research Phase  
**Created:** 2025-12-03  
**Goal:** Define the High-Level Design (HLD) for automated repository onboarding before diving into implementation details.

---

## 1. Problem Statement

Onboarding a new repository to LLMC currently involves too many manual steps:
1.  Run `llmc-rag-repo add` (creates workspace).
2.  Manually create/copy `llmc.toml` (project config).
3.  Update paths in `llmc.toml`.
4.  Run initial indexing.
5.  Configure enrichment.
6.  Restart daemon/tools.

This is error-prone and prevents adoption. We need a single command that handles this end-to-end.

## 2. Key Architectural Questions (Research Areas)

### 2.1 Configuration Architecture
-   **Workspace Config (`.rag/config/rag.yml`):** What is its role vs. project config?
-   **Project Config (`llmc.toml`):** How do we generate a portable version?
-   **Precedence:** How do these configs merge or layer?
-   **Templates:** Should we ship a "default" template? Where does it live?

### 2.2 Service Layer Orchestration
-   The CLI should be a thin wrapper.
-   We need a `RAGService.onboard_repo()` method.
-   What are the atomic steps of this method?
-   How do we handle failures/rollbacks?

### 2.3 User Experience (UX)
-   **Interactive Mode:** What questions do we ask?
-   **Non-Interactive Mode (`--yes`):** What are the sensible defaults?
-   **Progress Feedback:** How do we show long-running steps (indexing)?

## 3. Next Steps

1.  **Audit Current Config Loading:** Understand exactly how `tools/rag/config.py` loads and merges configs.
2.  **Define the "Portable Template":** Create a `llmc.toml` that works on `localhost` without user-specific hardcoding.
3.  **Draft HLD:** Create `DOCS/planning/HLD_Repo_Onboarding.md` covering:
    -   System Context Diagram
    -   Data Flow
    -   Component Interactions
4.  **Break Down SDDs:** Once HLD is approved, create SDDs for:
    -   Repo Configurator
    -   Service Orchestration
    -   CLI Integration
