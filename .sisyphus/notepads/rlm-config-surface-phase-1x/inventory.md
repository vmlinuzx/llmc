# RLM Config Inventory

**Generated**: 2026-01-25  
**Purpose**: Document all configurable RLM values surfaced in Phase 1.X

## Summary

**Total values inventoried**: 29

### Breakdown by Section
- `[rlm]` (Model selection): 2 values
- `[rlm.budget]`: 4 values
- `[rlm.sandbox]`: 4 values  
- `[rlm.llm.root]`: 2 values
- `[rlm.llm.sub]`: 2 values
- `[rlm.token_estimate]`: 2 values
- `[rlm.session]`: 4 values
- `[rlm.trace]`: 5 values
- Timeouts: 2 values
- Context limits: 2 values

---

## Inventory Table

| Value Name | Current Location | Canonical TOML Path | Legacy Alias | Default | Notes |
|------------|-----------------|---------------------|--------------|---------|-------|
| **Model Selection** |
| `root_model` | `config.py:RLMConfig.root_model` | `[rlm].root_model` | - | `"ollama_chat/qwen3-next-80b"` | Primary reasoning model |
| `sub_model` | `config.py:RLMConfig.sub_model` | `[rlm].sub_model` | - | `"ollama_chat/qwen3-next-80b"` | Sub-call model |
| **Budget Limits** |
| `max_session_budget_usd` | `config.py:RLMConfig.max_session_budget_usd` | `[rlm.budget].max_session_budget_usd` | `[rlm].max_session_budget_usd` | `1.00` | USD budget per session |
| `max_tokens_per_session` | `config.py:RLMConfig.max_tokens_per_session` | `[rlm.budget].max_session_tokens` | `[rlm].max_tokens_per_session` | `500_000` | Aliased to `max_session_tokens` |
| `max_subcall_depth` | `config.py:RLMConfig.max_subcall_depth` | `[rlm.budget].max_subcall_depth` | `[rlm].max_subcall_depth` | `5` | Max nested tool calls |
| `soft_limit_percentage` | `config.py:RLMConfig.soft_limit_percentage` | `[rlm.budget].soft_limit_percentage` | - | `0.80` | Warning threshold (80%) |
| **Sandbox Configuration** |
| `sandbox_backend` | `config.py:RLMConfig.sandbox_backend` | `[rlm.sandbox].backend` | `[rlm].sandbox_backend` | `"process"` | `"process"` or `"restricted"` |
| `security_mode` | `config.py:RLMConfig.security_mode` | `[rlm.sandbox].security_mode` | - | `"permissive"` | `"permissive"` or `"restrictive"` |
| `blocked_builtins` | `config.py:RLMConfig.blocked_builtins` | `[rlm.sandbox].blocked_builtins` | `[rlm].blocked_builtins` | 8 items | Blocked Python builtins (frozenset) |
| `allowed_modules` | `config.py:RLMConfig.allowed_modules` | `[rlm.sandbox].allowed_modules` | `[rlm].allowed_modules` | 13 items | Allowed Python modules (frozenset) |
| **LLM Parameters (Root)** |
| `root_temperature` | `config.py:RLMConfig.root_temperature` | `[rlm.llm.root].temperature` | `[rlm].root_temperature` | `0.1` | Sampling temperature for root model |
| `root_max_tokens` | `config.py:RLMConfig.root_max_tokens` | `[rlm.llm.root].max_tokens` | `[rlm].root_max_tokens` | `4096` | Max output tokens for root model |
| **LLM Parameters (Sub)** |
| `sub_temperature` | `config.py:RLMConfig.sub_temperature` | `[rlm.llm.sub].temperature` | `[rlm].sub_temperature` | `0.1` | Sampling temperature for sub model |
| `sub_max_tokens` | `config.py:RLMConfig.sub_max_tokens` | `[rlm.llm.sub].max_tokens` | `[rlm].sub_max_tokens` | `1024` | Max output tokens for sub model |
| **Token Estimation** |
| `chars_per_token` | `config.py:RLMConfig.chars_per_token` | `[rlm.token_estimate].chars_per_token` | `[rlm].chars_per_token` | `4` | Character-to-token ratio |
| `token_safety_multiplier` | `config.py:RLMConfig.token_safety_multiplier` | `[rlm.token_estimate].safety_multiplier` | `[rlm].token_safety_multiplier` | `1.2` | Safety margin for estimates (20%) |
| **Session Configuration** |
| `max_turns` | `config.py:RLMConfig.max_turns` | `[rlm.session].max_turns` | `[rlm].max_turns` | `20` | Max conversation turns |
| `session_timeout_seconds` | `config.py:RLMConfig.session_timeout_seconds` | `[rlm.session].session_timeout_seconds` | `[rlm].session_timeout_seconds` | `300` | Session timeout (5 minutes) |
| `max_context_chars` | `config.py:RLMConfig.max_context_chars` | `[rlm.session].max_context_chars` | `[rlm].max_context_chars` | `1_000_000` | Max context size |
| `max_print_chars` | `config.py:RLMConfig.max_print_chars` | `[rlm.session].max_output_chars` | `[rlm].max_print_chars` | `10_000` | Max output chars (aliased) |
| **Trace/Logging** |
| `trace_enabled` | `config.py:RLMConfig.trace_enabled` | `[rlm.trace].enabled` | `[rlm].trace_enabled` | `true` | Enable trace logging |
| `prompt_preview_chars` | `config.py:RLMConfig.prompt_preview_chars` | `[rlm.trace].prompt_preview_chars` | - | `200` | Prompt preview length |
| `response_preview_chars` | `config.py:RLMConfig.response_preview_chars` | `[rlm.trace].response_preview_chars` | - | `200` | Response preview length |
| `match_preview_chars` | `config.py:RLMConfig.match_preview_chars` | `[rlm.trace].match_preview_chars` | - | `200` | Search match preview length |
| `stdout_preview_chars` | `config.py:RLMConfig.stdout_preview_chars` | `[rlm.trace].stdout_preview_chars` | - | `2000` | Stdout preview length |
| **Timeouts** |
| `code_timeout_seconds` | `config.py:RLMConfig.code_timeout_seconds` | `[rlm.sandbox].code_timeout_seconds` | `[rlm].code_timeout_seconds` | `30` | Code execution timeout |

---

## Notes

### Implementation Status
- ✅ All values above are now in `RLMConfig` dataclass
- ⚠️ Nested parsing partially implemented in `load_rlm_config()`
- ⚠️ Legacy alias support NOT YET implemented (no deprecation warnings)
- ⚠️ Precedence rules (nested wins) NOT YET implemented

### Pricing (Special Case)
- Pricing configuration remains at `[rlm.pricing]` (handled by `budget.py:load_pricing()`)
- NOT included in this inventory (separate subsystem)
- Phase 1.X preserves existing pricing location

### Values NOT YET Surfaced
The following exist in code but are still hardcoded (future work):
- `llmc/rlm/prompts.py`: Prompt templates (not yet configurable)
- `llmc/rlm/nav/treesitter_nav.py`: Navigation chunk sizes, search limits
- Session trace formatting strings

### Comparison to Roadmap
Roadmap claimed "80+ values". Current count: **29 explicit config fields**.

The discrepancy likely includes:
- Prompt template components (strings, not scalar configs)
- Navigation/chunking parameters (still hardcoded)
- Individual pricing entries (separate table)
- Future expansion items

