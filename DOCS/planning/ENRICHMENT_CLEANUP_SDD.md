# Enrichment Script Cleanup SDD

## Goal Description
The goal is to remove hardcoded fallbacks and "Dave-specific" logic from `scripts/qwen_enrich_batch.py` to make the script more robust and environment-agnostic. The script should fail explicitly with helpful error messages if the necessary configuration (Ollama URL, model name) is missing, rather than silently falling back to `localhost` or default models.

## User Review Required
> [!IMPORTANT]
> This change will break existing workflows that rely on the implicit `localhost:11434` fallback or the default `qwen2.5:7b` model if they are not explicitly configured in the environment or `llmc.toml`. Users must ensure their environment is correctly configured.

## Proposed Changes

### `scripts/qwen_enrich_batch.py`

#### [MODIFY] `resolve_ollama_host_chain`
- Remove the logic that checks for `ATHENA_OLLAMA_URL` environment variable.
- This logic is specific to a particular environment and should be replaced by standard configuration methods.

#### [MODIFY] `_should_sample_local_gpu`
- Remove the default value `http://localhost:11434` for `OLLAMA_URL`.
- If `OLLAMA_URL` is not set and `host_url` is not provided, it should not assume localhost.

#### [MODIFY] `call_via_ollama`
- Remove the default value `http://localhost:11434` for `base_url`.
- Remove the default value `qwen2.5:7b-instruct-q4_K_M` for `model_name`.
- Raise a `ValueError` or `EnrichmentConfigError` if `base_url` or `model_name` cannot be resolved.

#### [MODIFY] `call_qwen`
- Ensure that if `backend="ollama"` (or auto-detected), the necessary parameters are present.
- If not, fail fast with a clear error message indicating which configuration is missing.

## Verification Plan

### Automated Tests
I will create a verification script `tests/verify_enrichment_cleanup.py` that uses `subprocess` to run `scripts/qwen_enrich_batch.py` under different conditions:

1.  **Missing Configuration**:
    - Run without `OLLAMA_URL` and without `OLLAMA_MODEL`.
    - Assert that the script fails with a specific error message about missing configuration.
2.  **Valid Configuration**:
    - Run with `OLLAMA_URL` and `OLLAMA_MODEL` set (e.g., to a mock or reachable server).
    - Assert that the script proceeds (or at least attempts to connect to the specified URL).

### Manual Verification
- Run the script manually with and without environment variables to confirm the behavior matches the automated tests.
