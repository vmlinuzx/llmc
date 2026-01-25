# RLM Configuration Reference

## Overview

RLM (Recursive Language Model) configuration is managed through the `[rlm]` section of `llmc.toml`. This allows fine-grained control over budgets, timeouts, model selection, and sandbox security policies.

## Quick Start

### Minimal Configuration

```toml
[rlm]
root_model = "ollama_chat/qwen3-next-80b"
sub_model = "ollama_chat/qwen3-next-80b"
```

All other settings use safe defaults.

### Local Development (Permissive)

```toml
[rlm]
root_model = "ollama_chat/qwen3-next-80b"
sub_model = "ollama_chat/qwen3-next-80b"

[rlm.sandbox]
security_mode = "permissive"  # Allow broad imports
code_timeout_seconds = 60

[rlm.budget]
max_session_budget_usd = 5.00
```

### Hospital/Production (Restrictive)

```toml
[rlm]
root_model = "deepseek/deepseek-reasoner"
sub_model = "deepseek/deepseek-reasoner"

[rlm.sandbox]
security_mode = "restrictive"  # Strict allowlist
code_timeout_seconds = 10
allowed_modules = ["json", "re", "math"]

[rlm.budget]
max_session_budget_usd = 0.10
max_tokens_per_session = 50000

[rlm.pricing]
"deepseek/deepseek-reasoner" = { input = 0.14, output = 2.19 }
```

## Configuration Sections

### [rlm] - Root Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `root_model` | string | `"ollama_chat/qwen3-next-80b"` | Model for root session calls |
| `sub_model` | string | `"ollama_chat/qwen3-next-80b"` | Model for recursive sub-calls |
| `root_temperature` | float | `0.1` | Temperature for root calls |
| `root_max_tokens` | int | `4096` | Max output tokens (root) |
| `sub_temperature` | float | `0.1` | Temperature for sub-calls |
| `sub_max_tokens` | int | `1024` | Max output tokens (sub) |

### [rlm.budget] - Cost & Token Limits

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_session_budget_usd` | float | `1.00` | Hard budget cap (USD) |
| `max_tokens_per_session` | int | `500000` | Token limit |
| `soft_limit_percentage` | float | `0.80` | Warning threshold (80% of budget) |
| `max_subcall_depth` | int | `5` | Max recursion depth |

### [rlm.sandbox] - Execution Security

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `security_mode` | string | `"permissive"` | `"permissive"` or `"restrictive"` |
| `code_timeout_seconds` | int | `30` | Sandbox code execution timeout |
| `max_output_chars` | int | `10000` | Max output per execution |
| `blocked_builtins` | list | see below | Forbidden builtins (both modes) |
| `allowed_modules` | list | see below | Allowlist for restrictive mode |

**Default blocked_builtins:**
```toml
["open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "exit", "quit"]
```

**Default allowed_modules (restrictive only):**
```toml
["json", "re", "math", "collections", "itertools", "functools", "operator", "string", "textwrap", "datetime", "copy", "typing", "dataclasses"]
```

#### Security Modes

- **Permissive:** Allows all imports; blocks dangerous builtins. For local development.
- **Restrictive:** Enforces `allowed_modules` allowlist + blocks builtins. For production/hospital deployments.

### [rlm.pricing] - Per-Model Pricing

```toml
[rlm.pricing]
default = { input = 0.01, output = 0.03 }
"ollama_chat/qwen3-next-80b" = { input = 0.0, output = 0.0 }  # Local = free
"deepseek/deepseek-reasoner" = { input = 0.14, output = 2.19 }
```

Prices are per-million tokens.

### [rlm.session] - Session Limits

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `session_timeout_seconds` | int | `300` | Overall session timeout (5 min) |
| `max_turns` | int | `20` | Max LLM conversation turns |

### [rlm.token_estimate] - Token Estimation

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `chars_per_token` | int | `4` | Character-to-token ratio |
| `token_safety_multiplier` | float | `1.2` | Safety margin for estimates |

### [rlm.trace] - Execution Tracing

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | Enable execution tracing |
| `prompt_preview_chars` | int | `200` | Max chars in prompt preview |
| `response_preview_chars` | int | `200` | Max chars in response preview |
| `stdout_preview_chars` | int | `2000` | Max chars in stdout preview |

## Validation

Configuration is validated on load:

- **Critical errors** (raise ValueError):
  - Negative budget or tokens
  - Invalid security_mode
  - Missing required pricing keys
  - chars_per_token < 1

- **Warnings** (log + use default):
  - Timeouts out of range
  - Preview sizes out of range

## CLI Usage

```bash
# Use default config discovery (./llmc.toml or ~/.llmc/llmc.toml)
llmc rlm query "What does this do?" --file mycode.py

# Specify custom config
llmc rlm query "Find bugs" --file buggy.py --config /path/to/llmc.toml

# Override budget via CLI
llmc rlm query "Analyze" --file big.py --budget 0.50
```

## Python API

```python
from llmc.rlm.config import load_rlm_config
from llmc.rlm.session import RLMSession

# Load from default location
config = load_rlm_config()

# Or specify path
config = load_rlm_config(Path("custom.toml"))

# Create session
session = RLMSession(config)
session.load_code_context("mycode.py")

# Run analysis
result = await session.run("Find all function definitions")
```

## See Also

- [RLM Architecture](../architecture/rlm.md)
- [RLM CLI Reference](../cli/rlm.md)
- [Budget Governance](../reference/budget.md)

## Migration Notes (Phase 1.X)

### Nested Configuration

Phase 1.X introduces nested TOML sections for better organization:

**Before (flat):**
```toml
[rlm]
root_model = "ollama_chat/qwen3-next-80b"
max_session_budget_usd = 1.00
max_tokens_per_session = 500000
code_timeout_seconds = 30
```

**After (nested):**
```toml
[rlm]
root_model = "ollama_chat/qwen3-next-80b"

[rlm.budget]
max_session_budget_usd = 1.00
max_tokens_per_session = 500000

[rlm.sandbox]
code_timeout_seconds = 30
```

### Backward Compatibility

**Flat keys still work** - you don't need to migrate immediately:

```toml
[rlm]
max_session_budget_usd = 2.00  # Still valid
```

However, nested keys take precedence:

```toml
[rlm]
max_session_budget_usd = 1.00  # Ignored

[rlm.budget]
max_session_budget_usd = 2.00  # This wins
```

### Alias Support

Some fields have canonical vs legacy names:

| Legacy Name | Canonical Name | Location |
|-------------|----------------|----------|
| `max_tokens_per_session` | `max_session_tokens` | `[rlm.budget]` |
| `max_print_chars` | `max_output_chars` | `[rlm.sandbox]` |

Both names work in Phase 1.X.

### Deprecation Timeline

- **Phase 1.X (current)**: Flat keys work, no warnings
- **Phase 1.X.1 (planned)**: Deprecation warnings added
- **Phase 2.0 (future)**: Flat keys removed, nested required

**Recommendation**: Migrate to nested structure when convenient, but no urgency.

### What Changed

1. **Config loading**: CLI now loads from `llmc.toml` by default
2. **Nested parsing**: All `[rlm.*]` sections are now parsed
3. **Validation**: Enhanced validation with clear error messages
4. **Defaults preserved**: No changes to default values

### Breaking Changes

**None** - Phase 1.X is fully backward compatible.

