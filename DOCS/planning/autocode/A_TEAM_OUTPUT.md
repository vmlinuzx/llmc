# A-Team Output: Phase 3.2 (Daemon Operations)

**Date:** 2025-12-16
**Author:** A-Team (Documentation Drafter)

---

## Deliverables

### 1. Requirements
- Created `DOCS/planning/autocode/REQUIREMENTS.md` defining scope and ACs.

### 2. Documentation
- Created `DOCS/operations/daemon.md`
    - Documented `llmc-cli service` commands (start, stop, status, logs).
    - Documented `llmc.toml` [daemon] configuration.
    - Explained Systemd integration and fallback modes.
    - **Decision:** Documented `llmc-cli service` instead of the raw `llmc-rag-daemon` script mentioned in the execution plan, as the CLI is the unified entry point and wraps the modern `tools.rag.service`.

---

## Terminology Decisions

- **RAG Daemon:** Refers to the background process managed by `llmc-rag-service`.
- **Event Mode:** The inotify-based operation mode.
- **Poll Mode:** The legacy scanning operation mode.

## Questions for B-Team

- The execution plan mentioned `llmc-rag-daemon` but the code points to `llmc-rag-service` (wrapped by `llmc-cli service`) being the modern implementation that respects `llmc.toml`. I proceeded with `llmc-cli service`. Please verify if this aligns with the long-term intent.

---
SUMMARY: Created daemon operations docs focusing on llmc-cli service and llmc.toml config, reconciling plan vs code reality.