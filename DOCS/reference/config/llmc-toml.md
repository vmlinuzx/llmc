# llmc.toml Reference

_Generated from `llmc.toml` on 2025-12-16 16:14_

This is an auto-generated reference of all configuration keys.
For a human-friendly guide, see [Configuration Guide](../../user-guide/configuration.md).

---

## [daemon]

| Key | Type | Value |
|-----|------|-------|
| `pycache_cleanup_days` | `int` | `7` |
| `mode` | `str` | `"event"` |
| `debounce_seconds` | `float` | `2.0` |
| `housekeeping_interval` | `int` | `300` |
| `nice_level` | `int` | `19` |
| `idle_backoff_max` | `int` | `2` |
| `idle_backoff_base` | `float` | `1.5` |

### [daemon.idle_enrichment]

| Key | Type | Value |
|-----|------|-------|
| `enabled` | `bool` | `true` |
| `batch_size` | `int` | `10` |
| `interval_seconds` | `int` | `600` |
| `preferred_chain` | `str` | `"code_enrichment_models"` |
| `code_first` | `bool` | `true` |
| `max_daily_cost_usd` | `float` | `1.0` |
| `dry_run` | `bool` | `false` |

## [docs]

### [docs.docgen]

| Key | Type | Value |
|-----|------|-------|
| `enabled` | `bool` | `false` |
| `backend` | `str` | `"shell"` |
| `output_dir` | `str` | `"DOCS/REPODOCS"` |
| `require_rag_fresh` | `bool` | `true` |

## [embeddings]

| Key | Type | Value |
|-----|------|-------|
| `default_profile` | `str` | `"docs"` |

### [embeddings.profiles]

| Key | Type | Value |
|-----|------|-------|

### [embeddings.routes]

| Key | Type | Value |
|-----|------|-------|

## [enrichment]

| Key | Type | Value |
|-----|------|-------|
| `default_chain` | `str` | `"code_enrichment_models"` |
| `batch_size` | `int` | `50` |
| `est_tokens_per_span` | `int` | `350` |
| `enforce_latin1_enrichment` | `bool` | `true` |
| `max_failures_per_span` | `int` | `4` |
| `enable_routing` | `bool` | `true` |

### [enrichment.routes]

| Key | Type | Value |
|-----|------|-------|
| `docs` | `str` | `"document_routes"` |
| `code` | `str` | `"code_enrichment_models"` |

### [enrichment.path_weights]

| Key | Type | Value |
|-----|------|-------|
| `src/**` | `int` | `1` |
| `lib/**` | `int` | `1` |
| `app/**` | `int` | `1` |
| `core/**` | `int` | `1` |
| `pkg/**` | `int` | `2` |
| `internal/**` | `int` | `2` |
| `cmd/**` | `int` | `2` |
| `**/tests/**` | `int` | `6` |
| `**/test/**` | `int` | `6` |
| `**/__tests__/**` | `int` | `6` |
| `*_test.py` | `int` | `6` |
| `test_*.py` | `int` | `6` |
| `*.test.ts` | `int` | `6` |
| `*.spec.js` | `int` | `6` |
| `docs/**` | `int` | `8` |
| `*.md` | `int` | `7` |
| `.github/**` | `int` | `9` |
| `examples/**` | `int` | `7` |
| `vendor/**` | `int` | `10` |
| `node_modules/**` | `int` | `10` |
| `third_party/**` | `int` | `10` |

## [indexing]

## [logging]

| Key | Type | Value |
|-----|------|-------|
| `max_file_size_mb` | `int` | `10` |
| `keep_jsonl_lines` | `int` | `1000` |
| `enable_rotation` | `bool` | `true` |
| `log_directory` | `str` | `"logs"` |
| `auto_rotation_interval` | `int` | `0` |

## [mcp]

| Key | Type | Value |
|-----|------|-------|
| `enabled` | `bool` | `true` |
| `config_version` | `str` | `"v0"` |

### [mcp.code_execution]

| Key | Type | Value |
|-----|------|-------|
| `enabled` | `bool` | `false` |
| `stubs_dir` | `str` | `".llmc/stubs"` |
| `sandbox` | `str` | `"subprocess"` |
| `timeout` | `int` | `30` |
| `max_output_bytes` | `int` | `65536` |
| `bootstrap_tools` | `list` | `['list_dir', 'read_file', 'execute_code']` |

### [mcp.server]

| Key | Type | Value |
|-----|------|-------|
| `transport` | `str` | `"stdio"` |
| `log_level` | `str` | `"info"` |

### [mcp.auth]

| Key | Type | Value |
|-----|------|-------|
| `mode` | `str` | `"none"` |

### [mcp.tools]

| Key | Type | Value |
|-----|------|-------|
| `allowed_roots` | `list` | `['/home/vmlinux/src']` |
| `enable_run_cmd` | `bool` | `true` |
| `read_timeout` | `int` | `10` |
| `exec_timeout` | `int` | `30` |

### [mcp.rag]

| Key | Type | Value |
|-----|------|-------|
| `jit_context_enabled` | `bool` | `true` |
| `default_scope` | `str` | `"repo"` |
| `top_k` | `int` | `3` |
| `token_budget` | `int` | `600` |

### [mcp.limits]

| Key | Type | Value |
|-----|------|-------|
| `max_request_bytes` | `int` | `262144` |
| `max_response_bytes` | `int` | `1048576` |

### [mcp.observability]

| Key | Type | Value |
|-----|------|-------|
| `enabled` | `bool` | `true` |
| `log_format` | `str` | `"json"` |
| `log_level` | `str` | `"info"` |
| `include_correlation_id` | `bool` | `true` |
| `metrics_enabled` | `bool` | `true` |
| `csv_token_audit_enabled` | `bool` | `true` |
| `csv_path` | `str` | `"./artifacts/mcp_token_audit.csv"` |
| `retention_days` | `int` | `0` |

## [medical]

### [medical.gated_formats]

| Key | Type | Value |
|-----|------|-------|

## [profiles]

### [profiles.daily]

| Key | Type | Value |
|-----|------|-------|
| `provider` | `str` | `"anthropic"` |
| `model` | `str` | `"claude-3-5-sonnet-latest"` |
| `temperature` | `float` | `0.3` |

### [profiles.yolo]

| Key | Type | Value |
|-----|------|-------|
| `provider` | `str` | `"minimax"` |
| `model` | `str` | `"m2-lite"` |
| `temperature` | `float` | `0.2` |

## [rag]

| Key | Type | Value |
|-----|------|-------|
| `enabled` | `bool` | `true` |

## [repository]

| Key | Type | Value |
|-----|------|-------|
| `domain` | `str` | `"medical"` |
| `medical_subtype` | `str` | `"clinical_note"` |
| `institution` | `str` | `"default"` |
| `default_domain` | `str` | `"medical"` |

### [repository.path_overrides]

| Key | Type | Value |
|-----|------|-------|
| `notes/**` | `str` | `"medical"` |
| `labs/**` | `str` | `"medical"` |
| `radiology/**` | `str` | `"medical"` |
| `discharge/**` | `str` | `"medical"` |

## [routing]

### [routing.slice_type_to_route]

| Key | Type | Value |
|-----|------|-------|
| `code` | `str` | `"code"` |
| `docs` | `str` | `"docs"` |
| `erp_product` | `str` | `"erp"` |
| `config` | `str` | `"docs"` |
| `data` | `str` | `"docs"` |
| `other` | `str` | `"docs"` |

### [routing.options]

| Key | Type | Value |
|-----|------|-------|
| `enable_query_routing` | `bool` | `true` |
| `enable_multi_route` | `bool` | `false` |

### [routing.multi_route]

| Key | Type | Value |
|-----|------|-------|

## [storage]

## [tool_envelope]

| Key | Type | Value |
|-----|------|-------|
| `enabled` | `bool` | `false` |
| `passthrough_timeout_seconds` | `int` | `30` |

### [tool_envelope.workspace]

| Key | Type | Value |
|-----|------|-------|
| `root` | `str` | `"/home/vmlinux/src/llmc"` |
| `respect_gitignore` | `bool` | `true` |
| `allow_outside_root` | `bool` | `false` |

### [tool_envelope.telemetry]

| Key | Type | Value |
|-----|------|-------|
| `enabled` | `bool` | `true` |
| `path` | `str` | `".llmc/te_telemetry.db"` |
| `capture_output` | `bool` | `true` |
| `output_max_bytes` | `int` | `8192` |

### [tool_envelope.grep]

| Key | Type | Value |
|-----|------|-------|
| `enabled` | `bool` | `true` |
| `preview_matches` | `int` | `10` |
| `max_output_chars` | `int` | `20000` |
| `timeout_ms` | `int` | `5000` |

### [tool_envelope.cat]

| Key | Type | Value |
|-----|------|-------|
| `enabled` | `bool` | `true` |
| `preview_lines` | `int` | `50` |
| `max_output_chars` | `int` | `30000` |

### [tool_envelope.agent_budgets]

| Key | Type | Value |
|-----|------|-------|
| `gemini-shell` | `int` | `900000` |
| `claude-dc` | `int` | `180000` |
| `qwen-local` | `int` | `28000` |
| `human-cli` | `int` | `50000` |
| `default` | `int` | `16000` |
