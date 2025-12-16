# Testing Report

## 1. Scope

- **Repo / project:** `llmc`
- **Feature / change under test:** Modular Embeddings Phase 1
- **Commit / branch:** `feature/modular-embeddings` (dirty)
- **Date / environment:** Friday, November 28, 2025 (Linux)

## 2. Summary

- **Overall assessment:** **CRITICAL FAILURES FOUND**. While the new `HashEmbeddingBackend` works as designed, the integration introduces a **blocking regression** that crashes the application for all standard (non-hash) embedding configurations. The `EmbeddingManager` cannot be instantiated with the default configuration.
- **Key risks:**
    - **Application Crash:** Any usage of `tools.rag.cli` or `EmbeddingManager` with default settings will raise a `ValueError`.
    - **Configuration Desync:** `tools.rag.config` and `tools.rag.embeddings` have incompatible definitions of "model presets".
    - **Linting Violations:** Significant number of static analysis errors (70+).

## 3. Environment & Setup

- **Commands run:**
    - `python3 tests/check_env.py` (Success)
- **Successes:** Python environment is valid, dependencies are importable.

## 4. Static Analysis

- **Tools run:** `ruff check tools/rag/embeddings.py tools/rag/embedding_providers.py`
- **Summary:** **70 Errors**.
    - Mostly `UP006` (Use `list` instead of `List`) and `UP035` (deprecated imports).
    - `I001` (Unsorted imports).
    - `UP045` (Optional syntax).
- **Notable files:** `tools/rag/embedding_providers.py` (heavily affected).

## 5. Test Suite Results

- **Unit Tests (`tests/test_embeddings_unit.py`):**
    - **Status:** PASS (4/4 tests)
    - **Notes:** Only tests `HashEmbeddingBackend` in isolation. Does not test integration.

- **Behavioral Tests (`tests/test_embeddings_behavior.py` - Created by Agent):**
    - **Status:** FAIL (2/5 tests)
    - **Failures:**
        - `test_factory_manager_fallback`: `ValueError: Unsupported embedding model preset: intfloat/e5-base-v2`.
        - `test_factory_dimension_mismatch_warning`: Originally failed due to test setup, but underlying code is unreachable in integration due to the configuration bug.

## 6. Behavioral & Edge Testing

- **Operation:** `tools.rag.cli search "test"` (Default Config)
    - **Scenario:** Happy Path (Default RAG search)
    - **Expected behavior:** Should initialize default provider (e5) and search.
    - **Actual behavior:** **CRASH**. `ValueError: Unsupported embedding model preset: intfloat/e5-base-v2`.
    - **Status:** **FAIL (BLOCKER)**

- **Operation:** `HashEmbeddingBackend` (Direct Usage)
    - **Scenario:** Determinism & Normalization
    - **Status:** PASS
    - **Notes:** Validated that the new hash backend works correctly when instantiated manually.

## 7. Documentation & DX Issues

- **Misleading Documentation:** `DOCS/Modular_Embeddings_Overview_Phase1.md` claims "For non-hash models: Behaviour remains the same... The same configuration functions and provider selection logic are used."
    - **Reality:** The provider selection logic in `tools/rag/embeddings.py` was rewritten and is now incompatible with `tools/rag/config.py`.

## 8. Most Important Bugs (Prioritized)

1.  **Title:** Default Configuration Crashes EmbeddingManager
    -   **Severity:** **Critical / Blocker**
    -   **Area:** RAG / Configuration
    -   **Repro steps:**
        1. Check out `feature/modular-embeddings`.
        2. Run `./scripts/te python3 -m tools.rag.cli search "foo"`.
    -   **Observed behavior:** `ValueError: Unsupported embedding model preset: intfloat/e5-base-v2`.
    -   **Evidence:** Traceback confirms `_build_provider_from_config` receives a model name string instead of expected preset types ("ollama", "sentence-transformer").

2.  **Title:** Static Analysis Regression
    -   **Severity:** Low (Technical Debt)
    -   **Area:** Code Quality
    -   **Observed behavior:** 70+ new ruff errors in modified files.

## 9. Coverage & Limitations

- **Not Tested:** Real interaction with Ollama or SentenceTransformers (blocked by Bug #1).
- **Assumptions:** Assumed `llmc.toml` or environment was intended to remain unchanged.
