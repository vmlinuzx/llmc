
# SDD – Config‑Driven Enrichment Chains (Phase 5)

**Status:** Draft  
**Owner:** Dave / LLMC Core  
**Related Branch:** `feature/enrichment-config-chains-phase5`  
**Prereqs:** Phase 1–4 (config loader stub, enrichment backends, cascade wiring into `qwen_enrich_batch.py`) integrated and green.

---

## 1. Overview

Phase 4 wired `scripts/qwen_enrich_batch.py` to a `BackendCascade` abstraction so all enrichment attempts now flow through a common backend interface rather than hard‑coded `call_qwen(...)` calls.

However, the *source of truth* for which models/backends are used, in what order, and with what failover semantics is still effectively:

- `PRESET_CACHE` in `qwen_enrich_batch.py` (7B vs 14B),
- ad‑hoc backend selection (`auto` / `ollama` / `gateway`),
- internal host chain lists in the script.

Phase 5 makes the enrichment behaviour **config‑driven**:

- `llmc.toml` (+ env overrides) defines one or more **named chains** of backends.
- Each chain entry specifies provider, model, URL, timeout, and routing tier.
- `config_enrichment` becomes the central loader/validator for that config.
- `qwen_enrich_batch` uses that config to build its `BackendCascade` per attempt.
- CLI/env can select which chain to use without editing Python.

The goal is: “If you want to change which models/backends the enrichment uses, you edit `llmc.toml` or set an env var, not `qwen_enrich_batch.py`.”

---

## 2. Current State (Baseline After Phase 4)

### 2.1 Backend & Cascade

- `tools.rag.enrichment_backends` defines:
  - `BackendAdapter` protocol.
  - `BackendCascade` orchestrator.
  - `AttemptRecord`, `BackendError` for structured error handling.

- `scripts/qwen_enrich_batch.py`:
  - Implements `_OllamaBackendAdapter` and `_GatewayBackendAdapter` as **local** adapter classes.
  - Uses `_build_cascade_for_attempt(...)` to create a `BackendCascade` for each attempt based on:
    - `tier_for_attempt` (`"7b"`, `"14b"`, `"nano"`),
    - CLI `--backend` (`auto`/`ollama`/`gateway`),
    - host chain (`ollama_host_chain`),
    - `PRESET_CACHE["7b"]` vs `PRESET_CACHE["14b"]` for options/model.

- Router logic decides when to promote from `"7b"` to `"14b"` (fallback tier) and when to move across Ollama hosts.

### 2.2 Config

- `llmc.toml` may have an `[enrichment]` section but is not yet the main driver for:
  - which backends are used,
  - chain order,
  - per‑entry provider/model/timeouts,
  - per‑run chain selection.
- Env override behaviour (`ENRICH_CHAIN_JSON`, etc.) is not yet fully defined or wired.

Result: There is a **config surface** but not a **config‑driven execution model**.

---

## 3. Goals & Non‑Goals

### 3.1 Goals

1. **Config‑driven chains**
   - Define a clear TOML schema for `[enrichment]` and `[[enrichment.chain]]` entries.
   - Allow multiple named chains; each chain is an ordered sequence of backends.
   - Each backend entry can specify provider, URL, model, timeout, options, and routing tier.

2. **Single source of truth**
   - `config_enrichment` is authoritative for enrichment chain configuration.
   - `qwen_enrich_batch` asks `config_enrichment` what chain to use and then builds a `BackendCascade` from it.

3. **Chain selection**
   - Let users choose a chain per run using CLI (`--chain-name`) and/or env (`ENRICH_CHAIN_NAME`).
   - Provide a sane default chain when nothing is configured.

4. **Env & scripting overrides**
   - Support `ENRICH_CHAIN_JSON` for injecting a chain definition via JSON.
   - Support env overrides for concurrency, cooldown, and chain name.

5. **Backwards‑compatible behaviour**
   - If `llmc.toml` is missing, malformed, or does not define a usable chain,
     `qwen_enrich_batch` falls back to the existing `PRESET_CACHE` + host chain logic.
   - Existing CLI flags (`--backend`, `--api`, `--local`) continue to behave as today
     for this phase; they are *interpreted via config* rather than hard‑wiring models.

6. **Better observability**
   - Metrics and ledger records know which chain and which chain entry was used
     for each attempt.

### 3.2 Non‑Goals

- Rewriting router heuristics (schema thresholds, line‑count promotion logic).
- Adding entirely new providers beyond the existing Ollama + gateway/Gemini path.
- Changing enrichment DB schemas or ledger JSON shapes in a breaking way.
- Implementing a UI for editing chains (TOML + env is sufficient for now).

---

## 4. Config Schema

### 4.1 TOML Layout

Extend/clarify `llmc.toml`:

```toml
[enrichment]
# Optional global defaults
default_chain = "default"
concurrency = 2
cooldown_seconds = 300

# Each [[enrichment.chain]] entry is one backend in a named chain.
[[enrichment.chain]]
chain = "default"                # which logical chain this belongs to
name = "athena-7b"               # stable identifier for metrics
provider = "ollama"              # "ollama" | "gateway" | "gemini" | ...
model = "qwen2.5:7b-instruct-q4_K_M"
url = "http://athena:11434"
routing_tier = "7b"              # which router tier this entry applies to
timeout_seconds = 45
enabled = true

  [enrichment.chain.options]
  num_ctx = 8192

[[enrichment.chain]]
chain = "default"
name = "gemini-fast"
provider = "gateway"
model = "gemini-2.5-flash"
routing_tier = "14b"             # used when router promotes to fallback tier
timeout_seconds = 45
enabled = true
```

**Notes:**

- `chain` (string): logical chain name (e.g. `"default"`, `"athena-only"`, `"mixed-local-plus-gemini"`).  
  - If omitted, default to `"default"`.

- `routing_tier` (string, optional): which router tier this entry participates in.  
  - For Phase 5, **use the existing tier labels**: `"7b"`, `"14b"`, `"nano"`.  
  - If omitted, treat as `"7b"` to preserve current behaviour.

- `provider` controls which adapter type is used:
  - `"ollama"` → `_OllamaBackendAdapter`
  - `"gateway"` / `"gemini"` → `_GatewayBackendAdapter` (via the gateway)
  - Future providers can map to new adapters in a later phase.

- `options` table is forwarded to the adapter as driver‑specific `ollama_options`
  or similar; its shape is not interpreted by `config_enrichment` beyond being a dict.

### 4.2 Env Overrides

Define the following env vars and their precedence (higher wins):

- `ENRICH_CHAIN_NAME`  
  - Overrides `--chain-name` default and `[enrichment].default_chain` when selecting a chain.

- `ENRICH_CHAIN_JSON`  
  - JSON document describing **one or more chains**.  
  - When set, overrides `[[enrichment.chain]]` entries **for the selected chain name**.  
  - Parsed and validated by `config_enrichment`. Invalid JSON → logged + ignored, fall back to TOML.

- `ENRICH_CONCURRENCY`  
  - Int; overrides `[enrichment].concurrency`.

- `ENRICH_COOLDOWN_SECONDS`  
  - Int; overrides `[enrichment].cooldown_seconds`.

- `ENRICH_CONFIG_PATH` (optional)  
  - Path to TOML file to use instead of the repo‑root `llmc.toml`.

**Precedence:**

1. CLI flags (`--chain-name`, future `--concurrency` / `--cooldown` if present).  
2. Env vars (`ENRICH_*`).  
3. TOML `[enrichment]` section.  
4. Hard‑coded defaults (single Ollama backend on `http://localhost:11434` and existing `PRESET_CACHE`).

---

## 5. Design & Components

### 5.1 `tools/rag/config_enrichment.py`

This module is the **single source of truth** for enrichment configuration.

#### 5.1.1 Data Structures

```python
@dataclass
class EnrichmentBackendSpec:
    name: str
    chain: str
    provider: str
    model: str | None
    url: str | None
    routing_tier: str | None
    timeout_seconds: int | None
    options: dict[str, object]
    enabled: bool = True


@dataclass
class EnrichmentConfig:
    default_chain: str
    concurrency: int
    cooldown_seconds: int
    chains: dict[str, list[EnrichmentBackendSpec]]
```

Optional helper type:

```python
class EnrichmentConfigError(ValueError):
    ...
```

#### 5.1.2 Public API

```python
def load_enrichment_config(
    repo_root: Path,
    *,
    toml_path: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> EnrichmentConfig:
    ...
```

- Responsibilities:
  - Locate TOML:
    - use `toml_path` if provided,
    - else `repo_root / "llmc.toml"` if it exists,
    - else treat as “no config” and return a minimal default.
  - Parse `[enrichment]` section and `[[enrichment.chain]]` entries.
  - Apply env overrides (`ENRICH_*`).
  - Validate:
    - Each backend spec must have `provider` and `name`.
    - At least one enabled `EnrichmentBackendSpec` in the default chain.
    - `routing_tier` must be one of `"7b"`, `"14b"`, `"nano"` (if set).
    - `provider` must be a known provider; unknown providers raise `EnrichmentConfigError`.
  - Return a fully populated `EnrichmentConfig`.

```python
def select_chain(
    config: EnrichmentConfig,
    chain_name: str | None,
) -> list[EnrichmentBackendSpec]:
    ...
```

- Responsibilities:
  - Determine effective chain name using:
    - explicit `chain_name` argument if provided,
    - else `ENRICH_CHAIN_NAME` (already baked into `config.default_chain`),
    - else `config.default_chain`.
  - Return the ordered list of **enabled** backends for that chain.
  - If chain does not exist or has no enabled entries:
    - Raise `EnrichmentConfigError` or, optionally, return `[]` and let caller fall back.

Optional helper for router tiers:

```python
def filter_chain_for_tier(
    chain: list[EnrichmentBackendSpec],
    routing_tier: str,
) -> list[EnrichmentBackendSpec]:
    ...
```

- Selects only the entries for a given tier (`"7b"`, `"14b"`, `"nano"`).  
- If none exist for that tier, returns `[]` and lets caller decide to fall back to
  legacy presets or to a default tier.

#### 5.1.3 Default/Fallback Behaviour

If no TOML is present, or `[enrichment]` is missing/invalid:

- `load_enrichment_config` returns an `EnrichmentConfig` approximating current behaviour:

```python
chains = {
    "default": [
        EnrichmentBackendSpec(
            name="default-ollama-7b",
            chain="default",
            provider="ollama",
            model=None,
            url=os.environ.get("ATHENA_OLLAMA_URL", "http://localhost:11434"),
            routing_tier="7b",
            timeout_seconds=None,
            options={},
            enabled=True,
        )
    ]
}
```

- `default_chain = "default"`
- `concurrency = 1`
- `cooldown_seconds = 0`

The router, host chain behaviour, and `PRESET_CACHE` continue to operate as before
for tiers whose config is missing.

---

### 5.2 `scripts/qwen_enrich_batch.py` Integration

Phase 4 introduced `_build_cascade_for_attempt(...)` to create a `BackendCascade`
per attempt based on router tiers, backend choice, and host chain. Phase 5 modifies
this function to use `EnrichmentConfig` where available.

#### 5.2.1 New Imports

At the top of `scripts/qwen_enrich_batch.py`:

```python
from tools.rag.config_enrichment import (
    EnrichmentConfig,
    EnrichmentBackendSpec,
    EnrichmentConfigError,
    load_enrichment_config,
    select_chain,
    filter_chain_for_tier,
)
```

#### 5.2.2 CLI Extensions

Extend `parse_args()` with:

```python
parser.add_argument(
    "--chain-name",
    type=str,
    default=None,
    help="Optional enrichment chain name from llmc.toml [enrichment.chain].",
)
parser.add_argument(
    "--chain-config",
    type=Path,
    default=None,
    help="Optional path to a TOML containing [enrichment] config (overrides repo llmc.toml).",
)
```

CLI resolution order for chain name:

1. `--chain-name` if set.
2. `ENRICH_CHAIN_NAME` (already folded into `EnrichmentConfig.default_chain`).
3. `config.default_chain`.
4. `"default"`.

#### 5.2.3 Loading Config in `main()`

In `main()`:

```python
config: EnrichmentConfig | None = None
try:
    config = load_enrichment_config(
        repo_root=args.repo,
        toml_path=args.chain_config,
    )
except EnrichmentConfigError as exc:
    # Log and fall back to legacy behaviour.
    print(f"[enrichment] config error: {exc} – falling back to presets.", file=sys.stderr)
    config = None

selected_chain: list[EnrichmentBackendSpec] | None = None
if config is not None:
    try:
        selected_chain = select_chain(config, args.chain_name)
    except EnrichmentConfigError as exc:
        print(f"[enrichment] chain selection error: {exc} – falling back to presets.", file=sys.stderr)
        selected_chain = None
```

These `config` / `selected_chain` values are then passed into `_build_cascade_for_attempt(...)`.

#### 5.2.4 Updating `_build_cascade_for_attempt`

Current signature (Phase 4):

```python
def _build_cascade_for_attempt(
    *,
    backend: str,
    tier_for_attempt: str,
    repo_root: Path,
    args: argparse.Namespace,
    ollama_host_chain: Sequence[Mapping[str, object]],
    current_host_idx: int,
    host_chain_count: int,
) -> tuple[BackendCascade, str, dict, str | None, str | None, str]:
    ...
```

New signature (Phase 5):

```python
def _build_cascade_for_attempt(
    *,
    backend: str,
    tier_for_attempt: str,
    repo_root: Path,
    args: argparse.Namespace,
    ollama_host_chain: Sequence[Mapping[str, object]],
    current_host_idx: int,
    host_chain_count: int,
    enrichment_config: EnrichmentConfig | None,
    selected_chain: Sequence[EnrichmentBackendSpec] | None,
) -> tuple[BackendCascade, str, dict, str | None, str | None, str, str | None]:
    ...
```

Return value gains an extra field: `chain_name_used` (or `None` when falling back).

Implementation logic:

1. **If `enrichment_config` and `selected_chain` are present:**

   - Derive tier‑specific subset:

     ```python
     tier_chain = filter_chain_for_tier(list(selected_chain), tier_for_attempt)
     ```

   - If `tier_chain` is non‑empty:
     - For each `EnrichmentBackendSpec` in `tier_chain`:
       - If `provider == "ollama"`:
         - Build an `_OllamaBackendAdapter` using:
           - `host_url = spec.url or ATHENA_OLLAMA_URL or "http://localhost:11434"`
           - `model_override = spec.model or tier preset model`
           - `options = spec.options` (falling back to preset options)
         - `host_label = spec.name` for metrics.
       - If `provider in {"gateway", "gemini"}`:
         - Build a `_GatewayBackendAdapter` with `config.model = spec.model`.
     - Build `BackendCascade(adapters=adapters)` from this list.

   - If `tier_chain` is empty, fall back to legacy behaviour for that tier (see below).

2. **If config is missing or unusable:**

   - Use the existing Phase‑4 logic:
     - `backend_choice = "gateway" if tier_for_attempt == "nano" else "ollama"`
     - `selected_backend = backend_choice if backend == "auto" else backend`
     - `preset_key = "14b" if tier_for_attempt == "14b" else "7b"`
     - `tier_preset = PRESET_CACHE[preset_key]`
     - Build a single `_OllamaBackendAdapter` or `_GatewayBackendAdapter`
       as in Phase 4.

3. **Return tuple:**

   ```python
   return cascade, preset_key, tier_preset, host_label, host_url, selected_backend, chain_name_used
   ```

The rest of the attempt loop remains unchanged: router logic, schema failure promotion, host chain fallback, and metrics/ledger recording all continue as before, now with additional metadata about which chain/entry was used.

#### 5.2.5 Metrics & Ledger Enrichment

When recording attempts and final ledger entries, include the following extra fields where possible:

- `chain_name` – name of the chain used.
- `backend_name` – `spec.name` of the backend that ultimately succeeded.
- (Optional later) `routing_tier` – tier at which the successful backend ran.

This is additive and should not break existing consumers of the metrics JSON.

---

### 5.3 Runner / Service Integration (Light Touch)

`tools/rag/runner.py` and `tools/rag/service.py` currently control when and how
`scripts/qwen_enrich_batch.py` is invoked.

For Phase 5:

- Prefer passing `--chain-name` rather than `--backend` when selecting different enrichment behaviours.
- Where concurrency/cooldown are used at the orchestration level:
  - Optionally call `load_enrichment_config` once at startup and use
    `config.concurrency` / `config.cooldown_seconds` as defaults.
  - Allow CLI/process flags to override as they already do.

Deep rework of runner/service is **not required** for this phase; wiring the chain selection is sufficient.

---

## 6. File‑Level Scope

1. **`tools/rag/config_enrichment.py`**
   - Define `EnrichmentBackendSpec`, `EnrichmentConfig`, `EnrichmentConfigError`.
   - Implement `load_enrichment_config`, `select_chain`, `filter_chain_for_tier`.
   - Handle TOML + env overrides and default/fallback behaviour.

2. **`scripts/qwen_enrich_batch.py`**
   - Import config types and functions.
   - Extend CLI with `--chain-name`, `--chain-config`.
   - Load enrichment config at startup.
   - Plumb `enrichment_config` / `selected_chain` into `_build_cascade_for_attempt`.
   - Update `_build_cascade_for_attempt` to use config where available and fall back to presets otherwise.
   - Add chain/entry metadata into attempt records and metrics where low‑risk.

3. **`tools/rag/runner.py`, `tools/rag/service.py`**
   - Prefer `--chain-name` in future wiring instead of `--backend` where appropriate.
   - Optionally fetch `concurrency` / `cooldown_seconds` from `load_enrichment_config`.

4. **Docs**
   - `scripts/rag/README.md` – document the new chain config and CLI flags.
   - `DOCS/design/HONEY_BADGER_ENRICHMENT.md` (or equivalent) – add examples for:
     - a single Athena chain,
     - a mixed local + Gemini fallback chain,
     - a gateway‑only chain.

---

## 7. Testing Strategy

### 7.1 Unit Tests

New or extended tests in `tests/test_enrichment_config.py`:

1. **TOML parsing**
   - Basic `[enrichment]` with one chain entry → correct `EnrichmentConfig`.
   - Multiple chains, with different `chain` names and `routing_tier` values.
   - `enabled = false` entries are skipped.

2. **Env overrides**
   - `ENRICH_CHAIN_NAME` changes default chain.
   - `ENRICH_CONCURRENCY` / `ENRICH_COOLDOWN_SECONDS` override TOML values.
   - `ENRICH_CHAIN_JSON` overrides TOML chain entries for a given chain.

3. **Validation**
   - Unknown `provider` → `EnrichmentConfigError`.
   - Invalid `routing_tier` → `EnrichmentConfigError`.
   - No enabled entries in default chain → `EnrichmentConfigError`.

4. **Tier filtering**
   - `filter_chain_for_tier(chain, "7b")` returns only entries whose `routing_tier == "7b"` or `None` (based on design).
   - If no entries for `"14b"`, returns an empty list (caller falls back to presets).

### 7.2 Integration‑Style Tests

In a new test file (e.g. `tests/test_enrichment_chain_integration.py`):

1. **Config→Cascade wiring (dry)**
   - Create a temporary TOML with:
     - `chain = "default"`,
     - one Ollama `routing_tier = "7b"`,
     - one gateway `routing_tier = "14b"`.
   - Use a fake `args` namespace and dummy `ollama_host_chain`.
   - Call `_build_cascade_for_attempt` (or a small wrapper) with:
     - `tier_for_attempt="7b"`, then `"14b"`.
   - Assert that the returned `BackendCascade.adapters` list has the expected provider mapping and order (can be checked via adapter types / config attributes, not actual network calls).

2. **Fallback behaviour**
   - No TOML present:
     - `load_enrichment_config` returns a default config.
     - `_build_cascade_for_attempt` behaves as the pre‑Phase‑5 logic (single Ollama/gateway adapter based on tier).

### 7.3 Smoke Tests

Manual / CI smoke:

- With a real or stubbed Ollama:

  ```bash
  python scripts/qwen_enrich_batch.py \
    --repo /path/to/repo \
    --chain-name default \
    --batch-size 3 \
    --dry-run \
    --verbose
  ```

- With a mixed local + gateway chain (if gateway is configured), ensure:
  - Router stays on 7B tier for small spans, using the primary Ollama entry.
  - For large or schema‑problematic spans, router promotes and gateway entry is used.

---

## 8. Rollout & Backwards Compatibility

- Phase 5 is designed to be **backwards compatible**:
  - If config is missing/invalid, existing behaviour remains via preset/host‑chain logic.
  - Existing CLI flags still work; new `--chain-name` / `--chain-config` flags are additive.
- Recommended rollout:
  1. Land the config loader and tests.
  2. Land the `qwen_enrich_batch` changes with fallback paths.
  3. Update docs and internal runbooks to use chains as the primary configuration concept.

Future phases can then safely:

- Move adapter classes out of `qwen_enrich_batch.py` into `tools.rag.enrichment_backends`.
- Introduce new providers and more sophisticated routing (per‑entry weights, feature flags, etc.)
- Tighten CLI/API surface by deprecating low‑level backend flags.
