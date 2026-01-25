# Configuration Guide

LLMC uses **TOML** for configuration with a cascading model:

1. **Global defaults** — Hardcoded in the application
2. **User Global** — `~/.llmc/config.toml` (optional)
3. **Repo Level** — `llmc.toml` in the repository root (recommended)

Repo-level settings override user-global settings, which override defaults.

---

## Quick Start

Create an `llmc.toml` in your repository root:

```toml
[rag]
enabled = true

[embeddings]
default_profile = "docs"

[embeddings.profiles.docs]
provider = "ollama"
model = "nomic-embed-text"
dimension = 768

[enrichment]
default_chain = "code_enrichment"
enable_routing = true
```

---

## Configuration Sections

### `[embeddings]`

Controls how content is converted to vector embeddings for semantic search.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_profile` | string | `"docs"` | Default embedding profile to use |

#### `[embeddings.profiles.<name>]`

Define named embedding profiles:

```toml
[embeddings.profiles.code]
provider = "ollama"           # "ollama", "openai", "hash" (testing)
model = "nomic-embed-text"    # Model identifier
dimension = 768               # Vector dimension (must match model)
cost_class = "low"            # Optional: "low", "medium", "high"
capabilities = ["code"]       # Optional: ["code", "docs", "medical"]

[embeddings.profiles.code.ollama]
api_base = "http://localhost:11434"
timeout = 120
```

#### `[embeddings.routes.<content_type>]`

Route different content types to specific profiles and indices:

```toml
[embeddings.routes.code]
profile = "code"          # Which profile to use
index = "emb_code"        # Index name in the database

[embeddings.routes.docs]
profile = "docs"
index = "embeddings"
```

---

### `[routing]`

Controls how content types are routed.

#### `[routing.slice_type_to_route]`

Maps slice types (detected during indexing) to route names:

```toml
[routing.slice_type_to_route]
code = "code"
docs = "docs"
config = "docs"
data = "docs"
other = "docs"
```

#### `[routing.options]`

```toml
[routing.options]
enable_query_routing = true   # Route queries based on detected content type
enable_multi_route = false    # Fan out to multiple routes (experimental)
```

#### `[routing.multi_route.<name>]`

Configure multi-route fan-out (when `enable_multi_route = true`):

```toml
[routing.multi_route.code_primary]
primary = "code"
secondary = [
  { route = "docs", weight = 0.5 }
]
```

---

### `[enrichment]`

Controls the LLM pipeline for generating span metadata (summaries, tags).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_chain` | string | — | Default chain when routing doesn't match |
| `batch_size` | int | `50` | Spans per enrichment batch |
| `est_tokens_per_span` | int | `350` | Estimated tokens per span (for cost) |
| `enforce_latin1_enrichment` | bool | `true` | Drop non-Latin chars to prevent DB poisoning |
| `max_failures_per_span` | int | `4` | Retries before giving up |
| `enable_routing` | bool | `true` | Enable content-type based chain routing |

#### `[enrichment.routes]`

Route content types to different enrichment chains:

```toml
[enrichment.routes]
docs = "document_routes"      # Chain name for documents
code = "code_enrichment"      # Chain name for code
```

#### `[[enrichment.chain]]`

Define enrichment chains (note: double brackets = array of tables):

```toml
[[enrichment.chain]]
name = "qwen3 4b"                  # Display name
chain = "code_enrichment"          # Chain group this belongs to
provider = "ollama"                # "ollama", "openai", "anthropic", "gemini", "minimax"
model = "qwen3:4b-instruct"        # Model identifier
url = "http://localhost:11434"     # API endpoint
routing_tier = "4b"                # Tier for fallback ordering: "4b" < "7b" < "14b" < "70b"
timeout_seconds = 90               # Request timeout
enabled = true                     # Enable/disable this chain
api_key_env = "OPENAI_API_KEY"     # Env var for API key (cloud providers)
options = { num_ctx = 8192, temperature = 0.2 }
```

**Fallback Behavior:** Chains in the same group are tried in order of `routing_tier` (smallest first). If one fails, the next tier is tried.

#### `[enrichment.path_weights]`

Prioritize which files get enriched first:

```toml
[enrichment.path_weights]
# Lower weight = higher priority (1-10)
"src/**"       = 1    # Core source: first
"lib/**"       = 1
"**/tests/**"  = 6    # Tests: deprioritized
"docs/**"      = 8    # Docs: low priority
"vendor/**"    = 10   # Vendor: last
```

---

### `[daemon]`

Controls the background indexing daemon.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `mode` | string | `"event"` | `"event"` (inotify) or `"poll"` (legacy) |
| `pycache_cleanup_days` | int | `7` | Delete old .pyc files (0 = disabled) |

#### Event Mode Settings

```toml
[daemon]
mode = "event"
debounce_seconds = 2.0          # Wait after file change before processing
housekeeping_interval = 300     # Periodic maintenance interval (seconds)
```

#### Poll Mode Settings

```toml
[daemon]
mode = "poll"
nice_level = 19                 # Process priority (0-19, higher = lower)
idle_backoff_max = 2            # Max multiplier when idle
idle_backoff_base = 1.5         # Gradual ramp
```

#### `[daemon.idle_enrichment]`

Run enrichment when daemon is idle:

```toml
[daemon.idle_enrichment]
enabled = true
batch_size = 10                       # Spans per idle cycle
interval_seconds = 600                # Min seconds between runs
preferred_chain = "code_enrichment"   # Which chain to use
code_first = true                     # Prioritize code over docs
max_daily_cost_usd = 1.00             # Stop if daily cost exceeds
dry_run = false                       # Log only, don't call LLM
```

---

### `[mcp]`

Model Context Protocol server configuration for Claude Desktop integration.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable MCP server |
| `config_version` | string | `"v0"` | Config schema version |

#### `[mcp.server]`

```toml
[mcp.server]
transport = "stdio"    # "stdio" for Claude Desktop
log_level = "info"     # "debug", "info", "warn", "error"
```

#### `[mcp.auth]`

```toml
[mcp.auth]
mode = "none"          # "none" (stdio), "bearer", "mtls"
```

#### `[mcp.tools]`

```toml
[mcp.tools]
allowed_roots = ["/home/user/src"]   # Filesystem access roots
enable_run_cmd = true                # Enable shell command execution
read_timeout = 10                    # File read timeout (seconds)
exec_timeout = 30                    # Command execution timeout
```

#### `[mcp.code_execution]`

Advanced: Anthropic "Code Mode" pattern (reduces tool count from 23 to 3):

```toml
[mcp.code_execution]
enabled = false               # Use classic mode for full capability
stubs_dir = ".llmc/stubs"     # Generated tool stubs
sandbox = "subprocess"        # "subprocess", "docker", "nsjail"
timeout = 30
max_output_bytes = 65536
bootstrap_tools = ["list_dir", "read_file", "execute_code"]
```

#### `[mcp.rag]`

```toml
[mcp.rag]
jit_context_enabled = true    # Just-in-time context injection
default_scope = "repo"        # "repo", "workspace", "global"
top_k = 3                     # Number of results to inject
token_budget = 600            # Max tokens for injected context
```

#### `[mcp.limits]`

```toml
[mcp.limits]
max_request_bytes = 262144    # 256KB
max_response_bytes = 1048576  # 1MB
```

#### `[mcp.observability]`

```toml
[mcp.observability]
enabled = true
log_format = "json"                  # "json" or "text"
log_level = "info"
include_correlation_id = true
metrics_enabled = true
csv_token_audit_enabled = true       # Token usage CSV trail
csv_path = "./artifacts/mcp_token_audit.csv"
retention_days = 0                   # 0 = keep forever
```


#### `[mcp.rlm]`

Enable the Recursive Loop Manager (RLM) tool.

```toml
[mcp.rlm]
enabled = false
max_loops = 5
timeout = 300
```
---

### `[tool_envelope]`

Shell middleware for intelligent output handling.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable tool envelope |
| `passthrough_timeout_seconds` | int | `30` | Passthrough mode timeout |

#### `[tool_envelope.workspace]`

```toml
[tool_envelope.workspace]
root = "/home/user/src/project"
respect_gitignore = true
allow_outside_root = false
```

#### `[tool_envelope.telemetry]`

⚠️ **Privacy Note:** When `capture_output = true`, command output is stored.

```toml
[tool_envelope.telemetry]
enabled = true
path = ".llmc/te_telemetry.db"
capture_output = true           # Store command output (privacy tradeoff)
output_max_bytes = 8192         # Max bytes to capture per command
```

#### `[tool_envelope.agent_budgets]`

Token budgets per agent type:

```toml
[tool_envelope.agent_budgets]
gemini-shell = 900000
claude-dc = 180000
qwen-local = 28000
human-cli = 50000
default = 16000
```

#### `[tool_envelope.grep]` / `[tool_envelope.cat]`

Per-command settings:

```toml
[tool_envelope.grep]
enabled = true
preview_matches = 10
max_output_chars = 20000
timeout_ms = 5000

[tool_envelope.cat]
enabled = true
preview_lines = 50
max_output_chars = 30000
```

---

### `[indexing]`

Controls file discovery during indexing.

```toml
[indexing]
exclude_dirs = [
    ".git",
    ".rag",
    "node_modules",
    "dist",
    "__pycache__",
    ".venv",
]
```

---

### `[logging]`

```toml
[logging]
max_file_size_mb = 10
keep_jsonl_lines = 1000
enable_rotation = true
log_directory = "logs"
auto_rotation_interval = 0     # 0 = disabled
```

---

### `[rag]`

```toml
[rag]
enabled = true
```

---

### `[docs.docgen]`

Documentation generation settings:

```toml
[docs.docgen]
enabled = false
backend = "shell"              # "shell", "llm", "http", "mcp"
output_dir = "DOCS/REPODOCS"
require_rag_fresh = true       # Only generate for indexed files

[docs.docgen.shell]
script = "scripts/docgen_stub.py"
timeout_seconds = 60
```

---

### `[repository]`

Domain-specific repository settings:

```toml
[repository]
domain = "code"                # "code", "docs", "medical"
default_domain = "code"

[repository.path_overrides]
"notes/**" = "medical"
"docs/**"  = "docs"
```

---

### `[profiles.<name>]`

Named runtime profiles for different operating modes:

```toml
[profiles.daily]
provider = "anthropic"
model = "claude-3-5-sonnet-latest"
temperature = 0.3

[profiles.daily.rag]
enabled = true

[profiles.yolo]
provider = "minimax"
model = "m2-lite"
temperature = 0.2
```

---

## Environment Variables

Many settings can be overridden via environment variables:

| Variable | Purpose |
|----------|---------|
| `LLMC_CONFIG` | Path to config file (overrides default) |
| `OLLAMA_HOST` | Ollama API base URL |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `GEMINI_API_KEY` | Google Gemini API key |

---

## Example Configurations

### Minimal (Local Ollama)

```toml
[embeddings]
default_profile = "local"

[embeddings.profiles.local]
provider = "ollama"
model = "nomic-embed-text"
dimension = 768

[enrichment]
default_chain = "local"

[[enrichment.chain]]
name = "local"
chain = "local"
provider = "ollama"
model = "qwen2.5:7b-instruct"
url = "http://localhost:11434"
routing_tier = "7b"
enabled = true
```

### Cloud Fallback

```toml
# Local primary
[[enrichment.chain]]
name = "local-4b"
chain = "enrichment"
provider = "ollama"
model = "qwen3:4b-instruct"
url = "http://localhost:11434"
routing_tier = "4b"
enabled = true

# DeepSeek fallback (cheap cloud)
[[enrichment.chain]]
name = "deepseek-fallback"
chain = "enrichment"
provider = "openai"
model = "deepseek-chat"
url = "https://api.deepseek.com/v1"
routing_tier = "70b"
enabled = true
api_key_env = "DEEPSEEK_API_KEY"
```

---

## See Also

- [Installation Guide](../getting-started/installation.md)
- [MCP Integration](../operations/mcp-integration.md)
- [Architecture Overview](../architecture/index.md)
