# SDD – Enrichment Config Loader (tools/rag/config_enrichment.py)

## 1. Scope

This SDD covers the introduction of a dedicated enrichment configuration loader:

- New module: `tools/rag/config_enrichment.py`
- New tests: `tests/test_enrichment_config.py`

It does **not** refactor `scripts/qwen_enrich_batch.py`, the daemon, or adapters yet. Those will consume this module in later patches.

## 2. Problem Statement

Today, enrichment backend selection and model names are hard-coded inside `scripts/qwen_enrich_batch.py` and partially in shell scripts / env conventions. This causes:

- Difficult experimentation with different backend chains (local 7B, local 14B, gateway/Gemini, etc.)
- Tight coupling between TOML/env surfaces and enrichment code
- Repeated logic for reading env/TOML

We want a single module that:

- Reads `[enrichment]` from `llmc.toml`
- Applies env overrides
- Produces a small, strongly-typed configuration object that downstream code can rely on.

## 3. Design Overview

### 3.1 Data structures

Two dataclasses describe the configuration:

```python
@dataclass
class BackendConfig:
    name: str
    provider: str           # "ollama" | "gateway" for now
    url: Optional[str]
    model: Optional[str]
    tier: Optional[str]
    timeout_seconds: float
    max_retries: int
    options: Dict[str, Any]
    keep_alive: Optional[str]


@dataclass
class EnrichmentConfig:
    concurrency: int
    cooldown_seconds: int
    batch_size: int
    est_tokens_per_span: int
    max_retries_per_span: int
    default_tier: str
    fallback_tier: str
    chain: List[BackendConfig]
```

These types are deliberately backend-agnostic. Adapter modules (added later) will use `BackendConfig` to build real API calls.

### 3.2 Config sources & precedence

Configuration comes from:

1. `llmc.toml` via `tools.rag.config.load_config(repo_root)`
2. Environment variables (via `env` mapping or `os.environ`)
3. Built-in defaults for enrichment

Precedence for scalars (highest → lowest):

- Env overrides:
  - `ENRICH_CONCURRENCY`
  - `ENRICH_COOLDOWN_SECONDS`
  - `ENRICH_BATCH_SIZE`
  - `ENRICH_MAX_RETRIES`
- TOML `[enrichment]` keys
  - `concurrency`
  - `cooldown_seconds`
  - `batch_size`
  - `max_retries_per_span`
- Built-in defaults
  - `DEFAULT_CONCURRENCY = 1`
  - `DEFAULT_COOLDOWN_SECONDS = 0`
  - `DEFAULT_BATCH_SIZE = 50`
  - `DEFAULT_MAX_RETRIES_PER_SPAN = 3`

`est_tokens_per_span` continues to use `tools.rag.config.get_est_tokens_per_span`, which already respects TOML with a default of `350`.

### 3.3 Chain config & defaults

The backend chain can be configured in two ways:

1. Env JSON override: `ENRICH_CHAIN_JSON` – a JSON array of backend entries.
2. TOML tables: `[[enrichment.chain]]` in `llmc.toml`.

Shape of each entry:

```toml
[[enrichment.chain]]
name = "athena-7b"
provider = "ollama"          # "ollama" | "gateway"
url = "http://athena:11434"  # optional
model = "qwen2.5:7b-instruct-q4_K_M"
tier = "7b"
timeout_seconds = 45
max_retries = 3

  [enrichment.chain.options]
  num_ctx = 8192
```

Validation rules:

- `name`: required non-empty string
- `provider`: required; must be one of `{ "ollama", "gateway" }`
- `options`: if present, must be a table/object
- `timeout_seconds`: coerced to float, default `60.0` on parse errors
- `max_retries`: coerced to int, clamped to `>= 0`, default `3`

If no chain is configured (neither TOML nor env), a **default local chain** is constructed:

- `BackendConfig(name="ollama-7b-default", provider="ollama", model=DEFAULT_7B_MODEL, tier="7b")`
- `BackendConfig(name="ollama-14b-fallback", provider="ollama", model=DEFAULT_14B_MODEL, tier="14b")`

These reuse **module-level defaults**:

```python
DEFAULT_7B_MODEL = "qwen2.5:7b-instruct-q4_K_M"
DEFAULT_14B_MODEL = "qwen2.5:14b-instruct-q4_K_M"
```

`qwen_enrich_batch.py` will later be refactored to import and use these instead of defining its own constants.

### 3.4 Public API

Single entry point:

```python
def load_enrichment_config(
    repo_root: Optional[Path] = None,
    env: Mapping[str, str] | None = None,
) -> EnrichmentConfig:
    ...
```

- When `repo_root` is None, it falls back to the same repo discovery used by `tools.rag.config.load_config`.
- When `env` is None, it uses `os.environ`.
- Raises `ValueError` if:
  - `ENRICH_CHAIN_JSON` is malformed JSON
  - `enrichment.chain` or the env override is not a non-empty list of tables
  - Any entry has an invalid provider or invalid `options` type

This isolates config-parsing errors in one place so callers can surface them cleanly.

## 4. Out of Scope

- Creating adapter classes (`OllamaBackendAdapter`, `GatewayBackendAdapter`)
- Rewriting `scripts/qwen_enrich_batch.py` to use this config
- Changing daemon / service wiring

Those are subsequent patches that will depend on this module.
