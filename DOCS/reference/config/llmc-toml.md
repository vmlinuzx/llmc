# llmc.toml Configuration Reference

Generated from `llmc/llmc.toml` default values.

## [storage]
| Key | Type | Example | Description |
|---|---|---|---|
| `index_path` | str | `.llmc/index_v2.db` | - |


## [logging]
| Key | Type | Example | Description |
|---|---|---|---|
| `log_directory` | str | `.llmc/logs` | - |
| `enable_rotation` | bool | `True` | - |
| `max_file_size_mb` | int | `10` | - |
| `keep_jsonl_lines` | int | `1000` | - |


## [indexing]
| Key | Type | Example | Description |
|---|---|---|---|
| `exclude_dirs` | list | `['.git', '.llmc', '.venv', '__pycache__', 'node...` | - |


## [embeddings]
| Key | Type | Example | Description |
|---|---|---|---|
| `default_profile` | str | `docs` | - |
| `profiles.docs.provider` | str | `ollama` | - |
| `profiles.docs.model` | str | `nomic-embed-text` | - |
| `profiles.docs.dimension` | int | `768` | - |


## [rag]
| Key | Type | Example | Description |
|---|---|---|---|
| `enabled` | bool | `True` | - |


## [enrichment]
| Key | Type | Example | Description |
|---|---|---|---|
| `path_weights.src/**` | int | `1` | - |
| `path_weights.lib/**` | int | `1` | - |
| `path_weights.app/**` | int | `1` | - |
| `path_weights.core/**` | int | `1` | - |
| `path_weights.pkg/**` | int | `2` | - |
| `path_weights.internal/**` | int | `2` | - |
| `path_weights.cmd/**` | int | `2` | - |
| `path_weights.**/tests/**` | int | `6` | - |
| `path_weights.**/test/**` | int | `6` | - |
| `path_weights.**/__tests__/**` | int | `6` | - |
| `path_weights.*_test.py` | int | `6` | - |
| `path_weights.test_*.py` | int | `6` | - |
| `path_weights.*.test.ts` | int | `6` | - |
| `path_weights.*.spec.js` | int | `6` | - |
| `path_weights.docs/**` | int | `8` | - |
| `path_weights.*.md` | int | `7` | - |
| `path_weights..github/**` | int | `9` | - |
| `path_weights.examples/**` | int | `7` | - |
| `path_weights.vendor/**` | int | `10` | - |
| `path_weights.node_modules/**` | int | `10` | - |
| `path_weights.third_party/**` | int | `10` | - |


## [mcp]
| Key | Type | Example | Description |
|---|---|---|---|
| `observability.enabled` | bool | `True` | - |
| `observability.log_format` | str | `json` | - |
| `observability.csv_token_audit_enabled` | bool | `True` | - |
| `observability.csv_path` | str | `./artifacts/mcp_token_audit.csv` | - |

