# Phase 2.1 Output: Installation Guide

**Date:** 2025-12-16
**Author:** A-Team
**Phase:** 2.1 — Installation Guide

---

## Sections Written/Revised

1. **Prerequisites:** Added Python 3.10+ and OS requirements.
2. **Quick Install:** Documented the `curl` installer script method.
3. **Manual Installation:** detailed `pip` install from git with `[rag,tui,agent]` extras.
4. **Developer Setup:** Added steps for cloning and editable install.
5. **Verification:** Added `llmc-cli --version` check.
6. **Troubleshooting:** Covered PATH issues and managed environment errors.

## Files Created/Modified

- `DOCS/planning/autocode/REQUIREMENTS.md` (Created)
- `DOCS/getting-started/installation.md` (Overwritten/Created)

## Terminology & Decisions

- **Package Name:** Clarified that while the PyPI/Project name is `llmcwrapper`, the installed binary is `llmc-cli`.
- **Python Version:** Recommended 3.10+ for best compatibility, though `pyproject.toml` allows >=3.9.
- **Install Method:** Prioritized the `curl` script as "Quick Install" per README, but provided robust `pip` instructions for power users.

## Blockers / Questions

- None.

---
SUMMARY: Wrote complete installation guide covering script, pip, and dev methods, matching 0.7.0 requirements.
