# Broken and Dead Code Audit

**Date:** 2025-05-23
**Auditor:** Jules

This document outlines the findings of an audit for broken and dead code in the repository.

## 1. Broken Configuration

### `pyproject.toml`
The configuration file `pyproject.toml` contains critical errors that prevent the package from being installed in editable mode (`pip install -e .`) and cause runtime failures.

*   **Missing Package Directories**: The `[tool.setuptools]` section lists `llmcwrapper` and `tools` as top-level packages:
    ```toml
    packages = ["llmcwrapper", "tools", "llmc_mcp", "llmc", "llmc.te", "llmc.te.handlers", "llmc_agent", "llmc_agent.backends"]
    ```
    However, the directories `llmcwrapper/` and `tools/` do not exist in the repository root. `tools` appears to have been moved (likely to `llmc/rag` or `llmc_mcp/tools`), but the configuration was not updated.
*   **Missing Dependencies**:
    *   The code in `llmc/commands/docs.py` imports `toml`:
        ```python
        import toml
        ```
        However, `pyproject.toml` only lists `tomli` and `tomli-w` as dependencies. `toml` is not installed, causing `ModuleNotFoundError`.
    *   `tree_sitter` and `tree_sitter_languages` are required by `llmc/rag` (and tests) but might be missing or version-mismatched in the environment if not explicitly installed matching the `optional-dependencies` exact versions.

## 2. Broken Code

### broken Imports (Missing `tools` package)
Several files attempt to import from the `tools` package, which no longer exists at the root.

*   **`scripts/llmc-route`**:
    This script injects the repo root into `sys.path` and attempts to import:
    ```python
    from tools.rag_router import route_query
    ```
    Since `tools` is missing, this script fails. It should likely import from `llmc.rag_router`.

### Broken CLI Commands
*   **`llmc/commands/docs.py`**:
    As noted above, this module fails to import due to the missing `toml` dependency. This breaks the `llmc docs` command group.

## 3. Broken Tests
The test suite is currently in a broken state due to the issues above and bad test practices.

*   **`tests/test_model_search_fix.py`**:
    This test file executes logic at the module level (during test collection) that requires a pre-existing RAG index:
    ```python
    results = search_spans("model", limit=5, repo_root=repo_root)
    ```
    This raises `FileNotFoundError` if the index does not exist, preventing test collection for the entire suite or causing immediate failure. Tests should not rely on external state being present at collection time.
*   **`tests/test_cli_p2_regression.py`**:
    Fails due to the `llmc.commands.docs` import error (missing `toml`).
*   **`tests/gap/security/test_hybrid_mode.py`**:
    Fails due to missing `mcp` dependency if not installed.
*   **`tests/rag/test_enrichment_budgets.py`**:
    Fails due to missing `tree_sitter` dependency if not installed.

## 4. Dead Code

### Unused/Missing Packages
*   **`llmcwrapper`**: Referenced in `pyproject.toml` as a package but the directory is missing. If this was intended to be the main wrapper, it is gone.
*   **`tools`**: Referenced in `pyproject.toml` and some scripts/docs, but the directory is missing. Its functionality seems to have migrated to `llmc/rag` and `llmc_mcp/tools`.

### Unused Scripts
*   **`scripts/p0_demo.py`**: This script appears to be a standalone demo that is not called by any other script, test, or documentation (except git internals). It imports `llmc.rag`, so it might work if `llmc` is in the path, but it seems abandoned.

### Zombie Code (Superseded but Active)
*   **`scripts/qwen_enrich_batch.py`**:
    Comments in `llmc/rag/enrichment_pipeline.py` state:
    > This pipeline replaces the monolithic qwen_enrich_batch.py script
    However, the script still exists and is heavily tested by `tests/test_qwen_enrich_batch_static.py` and `tests/test_enrichment_cascade_builder.py`. This suggests a partial migration where the old code is kept alive by its own tests despite being conceptually replaced.

## 5. Broken Documentation
*   **`DOCS/user-guide/enrichment/providers.md`**: References `from llmc.rag.enrichment_pipeline import EnrichmentPipeline`.
*   **`DOCS/user-guide/docgen.md`**: References `from llmc.rag.database import Database`.
*   **`llmc/docgen/README.md`**: References `from llmc.rag.database import Database`.

These import paths are invalid because `tools` is missing.
