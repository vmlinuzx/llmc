# Refactor Candidates: High Value Variables

## Overview

This document lists "high value" variables currently hardcoded in the codebase that should be moved to configuration files (e.g., `llmc.toml`, `rag_config.yaml`) or environment variables. This refactoring will improve portability, configurability, and maintainability.

## 1. Critical External Integrations

These values tie the codebase to specific external setups or user environments.

| File | Variable | Current Value | Recommendation |
| :--- | :--- | :--- | :--- |
| `tools/upload_context_to_gdrive.py` | `RCLONE_REMOTE` | `"dcgoogledrive:"` | Move to `llmc.toml` under `[backup]` or `[storage]`. |
| `tools/sync_to_gdrive.py` | `RCLONE_REMOTE` | `"dcgoogledrive:"` | Same as above. |
| `tools/upload_context_to_gdrive.py` | `DEFAULT_REMOTE_DIR` | `"llmc_backups"` | Move to `llmc.toml`. |

## 2. Model & Inference Configuration

Model names and parameters are scattered across scripts and tools.

| File | Variable | Current Value | Recommendation |
| :--- | :--- | :--- | :--- |
| `scripts/qwen_enrich_batch.py` | `DEFAULT_7B_MODEL` | `"qwen2.5:7b-instruct-q4_K_M"` | Move to `presets/` or `llmc.toml` `[enrichment]`. |
| `scripts/qwen_enrich_batch.py` | `DEFAULT_14B_MODEL` | `"qwen2.5:14b-instruct-q4_K_M"` | Same as above. |
| `scripts/qwen_enrich_batch.py` | `EST_TOKENS_PER_SPAN` | `350` | **Duplicated** in `tools/rag/cli.py`. Centralize in `tools/rag/config.py` or `llmc.toml`. |
| `scripts/qwen_enrich_batch.py` | `GATEWAY_DEFAULT_TIMEOUT` | `300.0` | Move to `llmc.toml` `[enrichment]`. |
| `tools/rag/config.py` | `MODEL_PRESETS` | (Hardcoded Dict) | Move to a standalone `presets.yaml` or `llmc.toml` to allow user extensibility without code changes. |
| `tools/rag/config.py` | `DEFAULT_GPU_MIN_FREE_MB` | `1536` | Move to `llmc.toml` `[embeddings]`. |

## 3. Indexing & RAG Policy

Core logic for how code is processed and indexed.

| File | Variable | Current Value | Recommendation |
| :--- | :--- | :--- | :--- |
| `scripts/rag/index_workspace.py` | `CHUNK_SIZE` | `1000` | Move to `llmc.toml` `[indexing]`. |
| `scripts/rag/index_workspace.py` | `CHUNK_OVERLAP` | `200` | Move to `llmc.toml` `[indexing]`. |
| `scripts/rag/index_workspace.py` | `EXCLUDE_DIRS` | (Set of dirs) | Move to `.geminiignore` style file or `llmc.toml` `exclude_patterns`. |
| `tools/rag/utils.py` | `EXCLUDE_DIRS` | (Set of dirs) | **Duplicated** logic. Unify with `index_workspace.py` via `llmc.toml`. |
| `tools/rag/workers.py` | `MAX_SNIPPET_CHARS` | `800` | Move to `llmc.toml`. |

## 4. Proposed `llmc.toml` Schema Extensions

To accommodate these, we should expand `llmc.toml`:

```toml
[backup]
remote_name = "dcgoogledrive:"  # Was RCLONE_REMOTE
remote_dir = "llmc_backups"

[enrichment]
# Centralize model choices here
default_model = "qwen2.5:7b-instruct-q4_K_M"
large_model = "qwen2.5:14b-instruct-q4_K_M"
timeout = 300.0
est_tokens_per_span = 350

[indexing]
chunk_size = 1000
chunk_overlap = 200
max_snippet_chars = 800
exclude_dirs = [".git", ".rag", "node_modules", "__pycache__"]

[embeddings]
gpu_min_free_mb = 1536
```

## 5. Action Plan

1.  **Unify Duplication:** Fix `EST_TOKENS_PER_SPAN` (scripts vs tools) and `EXCLUDE_DIRS` (indexing vs utils) immediately.
2.  **Config Loader:** Update `tools/rag/config.py` or `llmc/client.py` to read these new sections from `llmc.toml`.
3.  **Migration:** Replace hardcoded constants in python files with lookups to the config loader.
