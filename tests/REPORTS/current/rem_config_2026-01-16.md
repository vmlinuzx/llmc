# Config Demon Report - 2026-01-16

This report validates `llmc.toml` against the known schema and best practices, focusing on recently modified files and related feature configurations.

## Summary

| Severity | Count | Finding |
| -------- | ----- | ------------------------------------------------------------------ |
| **P2**   | 1     | Stale documentation for `llmc.toml` schema.                        |
| **Info** | 1     | Modified `llmc.toml` contains valid, undocumented configuration.   |
| **Info** | 1     | Modified `llmc/rag/skeleton.py` is unrelated to config changes.    |

---

## Findings

### 1. P2: Stale Configuration Schema Documentation

- **Finding:** The primary configuration reference at `DOCS/reference/config/llmc-toml.md` is out of date. It is missing schema information for the new REST API v1 feature, which has been implemented and is configurable via `llmc.toml`.
- **Evidence:**
    - The schema reference was last generated on 2025-12-16.
    - Recent commits (`6191a5b`, `9ddb9af`) introduced the REST API v1 feature.
    - The configuration loading code at `llmc_mcp/config.py` explicitly defines and loads `RestApiConfig` and `WorkspacesConfig` dataclasses.
    - The High-Level Design document at `DOCS/architecture/HLD-REST-API-v1.md` specifies the exact schema that is missing from the reference documentation.
- **Impact:** Developers and users cannot discover or validate the new REST API configuration settings from the primary reference document. This leads to confusion and makes configuration difficult without reading the source code or design documents.
- **Recommendation:** The documentation generation script (`scripts/generate_config_docs.py`) should be updated and re-run to ensure `DOCS/reference/config/llmc-toml.md` reflects the current, complete schema, including the `[mcp.rest_api]` and `[mcp.workspaces]` sections.

### 2. Info: Modified `llmc.toml` Contains Valid Configuration

- **Finding:** The modified `llmc.toml` file contains new configuration sections: `[mcp.rest_api]` and `[mcp.workspaces]`.
- **Analysis:**
    - These keys are not present in the outdated `DOCS/reference/config/llmc-toml.md`.
    - However, they are explicitly defined in the feature's High-Level Design (`DOCS/architecture/HLD-REST-API-v1.md`) and are correctly parsed by the configuration loader at `llmc_mcp/config.py`.
- **Conclusion:** The configuration is **valid and correct** for the new feature. The issue lies with the documentation, not the configuration file itself.

### 3. Info: Modified `llmc/rag/skeleton.py` Unrelated to Config

- **Finding:** The file `llmc/rag/skeleton.py` was also modified recently.
- **Analysis:** An inspection of this file reveals it is a code skeletonization utility that uses `tree-sitter`. It does not read from or depend on `llmc.toml` or any of the new REST API configurations.
- **Conclusion:** This file modification is not related to the configuration validation task.