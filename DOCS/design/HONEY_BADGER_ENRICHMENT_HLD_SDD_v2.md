# Honey Badger Enrichment – Configurable Backend Chain

_Status: HLD + SDD v2 (draft)_

---

## 1. Goals

- Replace hard‑coded models, backends and gateway paths in:
  - `scripts/qwen_enrich_batch.py`
  - `tools/rag/runner.py`
  - `tools/rag/service.py`
- Drive enrichment through a **configurable, ordered failover chain** of LLM backends:
  - local Ollama,
  - JS gateway (OpenAI / Gemini / Azure),
  - future direct APIs.
- Preserve existing behaviour (“7B first, promote to 14B on size / validation failure”) as the **default config**, not baked into code.
- Make config editable by normal humans (`llmc.toml` + env), with a clean path to per‑repo overrides.
- Improve observability: every enrichment attempt is tied to a specific backend entry (name, provider, model, host, latency, failure reason).

Non‑goals for this patch:

- Implement every provider type; we start with `ollama` + `gateway` and define an interface for `gemini`, `openai`, etc.
- Rewrite router heuristics from scratch; we re‑express them in terms of the chain but keep the core “promote on size / schema / repeated failure” semantics.

---

## 2. Architecture Overview

High‑level pieces:

1. **Config Loader** – `tools/rag/config_enrichment.py`  
   - Reads `[enrichment]` from `llmc.toml` at repo root.  
   - Applies environment overrides (e.g. `ENRICH_CHAIN_JSON`, `ENRICH_CONCURRENCY`, `ENRICH_COOLDOWN_SECONDS`).  
   - Produces a strongly‑typed `EnrichmentConfig` object used everywhere else.

2. **Backend Adapters** – `tools/rag/enrichment_backends.py`  
   - Defines a `BackendAdapter` protocol and concrete adapters for:
     - `OllamaBackendAdapter` – wraps existing `call_via_ollama` and `resolve_ollama_host_chain` behaviour.
     - `GatewayBackendAdapter` – wraps existing `call_via_gateway` behaviour (Azure / Gemini / OpenAI via `llm_gateway.js`).  
   - Later providers (e.g. `GeminiBackendAdapter`, `OpenAIBackendAdapter`) plug into the same interface without touching `qwen_enrich_batch.py`.

3. **Backend Cascade** – also in `enrichment_backends.py`  
   - `BackendCascade` owns an ordered list of adapters derived from `EnrichmentConfig`.  
   - For each span, it:
     - chooses a starting index based on router policy,
     - iterates over the configured backends with per‑backend retry & timeout,
     - returns the first valid `(text, meta, attempt_records)` triple, or raises a structured error after exhausting the chain.

4. **Enrichment Driver** – `scripts/qwen_enrich_batch.py`  
   - Continues to own:
     - fetching spans from DB,
     - building prompts,
     - calling `parse_and_validate`,
     - writing enrichments back,
     - emitting metrics and ledger logs.
   - Delegates **all backend/model decisions** to `EnrichmentConfig` + `BackendCascade`.  
   - Old tier logic (`start_tier`, `policy_default_tier`, `policy_fallback_tier`, `"nano"` gateway tier) is replaced by chain‑aware routing that maps router decisions to chain indices.

5. **Daemon + Runner Integration**  
   - `tools/rag/runner.run_enrich` becomes a thin wrapper that just invokes the script and lets config drive everything.  
   - `tools/rag/service`:
     - reads `[enrichment]` for batch size, cooldown, and enabled flag,
     - calls `run_enrich` without backend/tier CLI plumbing,
     - surfaces config errors as actionable messages.

---

## 3. Config Surface (llmc.toml)

### 3.1 Schema

We extend the existing `[enrichment]` section:

```toml
[enrichment]
enabled = true              # default: true
batch_size = 50             # existing field, still honored
est_tokens_per_span = 350   # existing field, still honored
concurrency = 1             # max concurrent spans per process
cooldown_seconds = 300      # minimum age of a file before re‑enrich
max_retries_per_span = 3    # upper bound; router policy may cap lower

# Optional: explicit router defaults (fallbacks to router/policy.json)
default_tier = "7b"         # logical tier label
fallback_tier = "14b"

# Ordered chain of backends
[[enrichment.chain]]
name = "athena-7b"
provider = "ollama"         # "ollama" | "gateway" | future providers
url = "http://athena:11434" # optional; if omitted, use ENRICH_OLLAMA_HOSTS / ATHENA_OLLAMA_URL / OLLAMA_URL
model = "qwen2.5:7b-instruct-q4_K_M"
tier = "7b"                 # optional logical tier label for router mapping
timeout_seconds = 45
max_retries = 3
keep_alive = "5m"           # passed through to Ollama options if supported

  [enrichment.chain.options]
  num_ctx = 8192
  num_thread = 8
  num_batch = 2

[[enrichment.chain]]
name = "gemini-fast"
provider = "gateway"        # uses llm_gateway.js; model/name resolved via env
model = "gemini-2.5-flash"  # recorded for observability; effective model comes from gateway config
tier = "14b"                # acts as “fallback” tier in router mapping
timeout_seconds = 60
max_retries = 2
```

Notes:

- There is **a single ordered chain** per repo in this patch. Multi‑chain support (e.g. “cheap‑only” vs “production”) can be added later by introducing a `profile` key.
- Existing keys (`batch_size`, `est_tokens_per_span`, commented `model`) remain valid; if `[[enrichment.chain]]` is missing we construct a default chain from them (see 3.3).

### 3.2 Environment Overrides

Config precedence (highest → lowest):

1. **Env JSON override**:
   - `ENRICH_CHAIN_JSON` – JSON array of backend configs with the same shape as `[[enrichment.chain]]` entries.
   - Useful for one‑off experiments or CI without editing `llmc.toml`.

2. **Scalar env overrides**:
   - `ENRICH_CONCURRENCY` → overrides `[enrichment].concurrency`.
   - `ENRICH_COOLDOWN_SECONDS` → overrides `[enrichment].cooldown_seconds`.
   - `ENRICH_MAX_RETRIES` → overrides `[enrichment].max_retries_per_span`.
   - `ENRICH_BATCH_SIZE` → overrides `[enrichment].batch_size` (daemon already uses this semantics).

3. **Ollama host discovery env** (used only if a backend’s `provider = "ollama"` and `url` is empty):
   - `ENRICH_OLLAMA_HOSTS`
   - `ATHENA_OLLAMA_URL`
   - `OLLAMA_URL`, `OLLAMA_HOST_LABEL`  
   These are wired via the existing `resolve_ollama_host_chain` helper and preserved for backwards compatibility.

4. **TOML defaults**:
   - Values in `[enrichment]` and `[[enrichment.chain]]`.

5. **Code defaults** when there is no TOML or env:
   - concurrency = 1
   - cooldown_seconds = 0
   - max_retries_per_span = 3
   - an implicit “7B Ollama on localhost” chain entry.

### 3.3 Default Chain Construction

If **no chain entries** are configured (neither TOML nor `ENRICH_CHAIN_JSON`), the loader builds a default chain that mirrors current behaviour:

```toml
[[enrichment.chain]]
name = "ollama-7b-default"
provider = "ollama"
tier = "7b"
model = "qwen2.5:7b-instruct-q4_K_M"   # from DEFAULT_7B_MODEL constant
timeout_seconds = 300

[[enrichment.chain]]
name = "ollama-14b-fallback"
provider = "ollama"
tier = "14b"
model = "qwen2.5:14b-instruct-q4_K_M"   # from DEFAULT_14B_MODEL
timeout_seconds = 300
```

These defaults are defined in `config_enrichment.py`; `qwen_enrich_batch.py` no longer hardcodes `DEFAULT_7B_MODEL` / `DEFAULT_14B_MODEL` itself.

---

## 4. Backend Adapters & Cascade

### 4.1 Types

In `tools/rag/enrichment_backends.py`:

```python
from dataclasses import dataclass
from typing import Any, Dict, Protocol, Tuple, List, Optional

@dataclass
class BackendConfig:
    name: str
    provider: str               # "ollama", "gateway", etc.
    url: Optional[str]
    model: Optional[str]
    tier: Optional[str]         # "7b", "14b", "nano", etc., for router mapping
    timeout_seconds: float
    max_retries: int
    options: Dict[str, Any]
    keep_alive: Any | None

class BackendError(Exception):
    # Raised when a backend fails in a way that should trigger failover.
    pass

class BackendAdapter(Protocol):
    config: BackendConfig

    def generate(self, prompt: str) -> Tuple[str, Dict[str, Any]]:
        # Return (raw_text, meta). Should raise BackendError on retryable errors.
        ...
@dataclass
class AttemptRecord:
    backend_name: str
    provider: str
    model: str | None
    duration_sec: float
    success: bool
    failure_type: str | None   # "network", "timeout", "parse", "schema", etc.
    error_message: str | None
    host: str | None
    gpu_stats: Dict[str, Any] | None
```

Meta from adapters should include, at minimum, `backend`, `provider`, `model`, `host`, plus any existing fields (e.g. `eval_count`, `options`, `base_url`).

### 4.2 Concrete Adapters

**OllamaBackendAdapter**

- Wraps existing `call_via_ollama` function:
  - `base_url` comes from `config.url` or (if empty) from `resolve_ollama_host_chain` logic.
  - `model_override` comes from `config.model`.
  - `options`, `keep_alive` passed through.
- Converts low‑level errors (`URLError`, JSON decode, no response) into `BackendError` with a sensible `failure_type` and message.
- Ensures meta contains:
  - `backend = "ollama"`,
  - `provider = "ollama"`,
  - `model`, `base_url`, `host`.

**GatewayBackendAdapter**

- Wraps existing `call_via_gateway` function:
  - `gateway_path` remains `REPO_ROOT / "scripts" / "llm_gateway.js"` by default; we can make this overridable later if needed.
  - Timeout comes from `config.timeout_seconds`.
- Uses `GEMINI_MODEL` / `AZURE_OPENAI_DEPLOYMENT` envs exactly as the existing code does to derive an effective model name for meta.
- Ensures meta contains:
  - `backend = "gateway"`,
  - `provider = "gateway"`,
  - `model = <resolved model from env>`.

### 4.3 BackendCascade

```python
@dataclass
class BackendCascade:
    backends: List[BackendAdapter]

    def generate_for_span(self, prompt: str, *, start_index: int = 0) -> tuple[str, Dict[str, Any], List[AttemptRecord]]:
        attempts: List[AttemptRecord] = []
        last_error: Exception | None = None

        for idx in range(start_index, len(self.backends)):
            backend = self.backends[idx]
            attempt_start = time.monotonic()
            try:
                text, meta = backend.generate(prompt)
                duration = time.monotonic() - attempt_start
                attempts.append(
                    AttemptRecord(
                        backend_name=backend.config.name,
                        provider=backend.config.provider,
                        model=meta.get("model"),
                        duration_sec=duration,
                        success=True,
                        failure_type=None,
                        error_message=None,
                        host=meta.get("host"),
                        gpu_stats=meta.get("gpu_stats"),
                    )
                )
                return text, meta, attempts
            except BackendError as exc:
                duration = time.monotonic() - attempt_start
                # map exc → failure_type
                attempts.append(...)
                last_error = exc
                continue

        raise BackendError("All backends in chain failed") from last_error
```

The cascade doesn’t know about spans or router; it is given a `start_index` and returns detailed attempt records for metrics.

---

## 5. Router & Promotion Semantics

We keep current router behaviour conceptually but shift it onto the chain:

- `router/policy.json` still defines:
  - `default_tier` / `fallback_tier`
  - `promote_if.span_line_count_gte`
  - `promote_if.schema_failures_gte`
  - `max_retries_per_span`
- `scripts/router.py` still computes `RouterSettings` and `choose_start_tier` based on metrics (`line_count`, `tokens_in`, etc.).

**New mapping layer in `qwen_enrich_batch.py`:**

- After computing `router_metrics`, we call `choose_start_tier` as today and get a tier label: `"7b"`, `"14b"`, or `"nano"`.
- We map that tier label to a chain index:

```python
def find_chain_index_for_tier(chain: list[BackendConfig], tier: str, default: int = 0) -> int:
    for idx, cfg in enumerate(chain):
        if cfg.tier and cfg.tier.lower() == tier.lower():
            return idx
    return default
```

- `start_index` passed into `BackendCascade.generate_for_span` is the index returned by this function.
- Promotion logic (schema failures, size, runtime failures) no longer switches between hardcoded `"7b"` / `"14b"` tiers; instead it **moves the chain index forward**:
  - On promotion, set `current_index = max(current_index + 1, fallback_index)` and retry.
  - The “fallback tier” from policy is used only to pick a *floor* chain index; if there is no backend with that tier, we fall back to the last configured backend.

This keeps the “cheap → expensive” story but lets that mapping be data‑driven.

---

## 6. Enrichment Driver Changes (qwen_enrich_batch.py)

Key changes:

1. **Centralize config**  
   - At startup:
     - Resolve `repo_root` with `ensure_repo()`.
     - Call `load_enrichment_config(repo_root)` from `tools.rag.config_enrichment`.
     - Build `BackendConfig` objects from the resulting config and instantiate adapters.
     - Construct `BackendCascade` once and reuse for all spans.

2. **Remove hard‑coded models / tiers from the main loop**  
   - `DEFAULT_7B_MODEL`, `DEFAULT_14B_MODEL`, `RAG_FALLBACK_MODEL`, and the `"nano" = gateway` special case are moved into:
     - defaults used by `config_enrichment` when building implicit chains,
     - optional constants used only for that purpose.
   - The main enrichment loop no longer branches on `"gateway"` vs `"ollama"` directly; it just:
     - computes `start_index` from router tier,
     - calls `cascade.generate_for_span(prompt, start_index=start_index)`.

3. **CLI arguments become config overrides instead of control flow**  
   - Keep flags for backwards compatibility, but reinterpret them:
     - `--backend`, `--api`, `--local`:
       - Set a filter on allowed providers (`["ollama"]`, `["gateway"]`, or both).
       - If the requested provider isn’t present in the chain, fail fast with a clear message.
     - `--model`:
       - Acts as a *recorded* model label for metrics when config entries don’t specify one explicitly.
     - `--fallback-model`:
       - Only used when auto‑building the default chain in the absence of `[enrichment.chain]`. If the chain is explicitly configured, this flag has no effect.
     - `--gateway-path`:
       - Remains as an escape hatch but is now plumbed into `GatewayBackendAdapter` rather than used throughout the script.
     - `--start-tier`, `--router`, `--max-tokens-headroom`:
       - Continue to feed router settings as today but ultimately drive chain index instead of tier labels.

4. **Metrics & ledger**  
   - `metrics_summary` gains:
     - `backend_name` – configured name, e.g. `"athena-7b"`.
     - `backend_provider` – `"ollama"`, `"gateway"`, etc.
   - `ledger_record` gains:
     - `backend` – same as `backend_name`.
     - `provider` – same as `backend_provider`.
   - `attempt_records` from the cascade are used to:
     - compute `attempts` (existing field),
     - attach per‑backend failure info when debug logging is enabled.

5. **“Honey Badger loop” observability**  
   - When we fall through the chain and restart (due to backoff policy), log a single concise message:
     - `"[HB] Restarting enrichment chain from index 0 after cooldown: last_failure=runtime/timeout/schema"`.

---

## 7. Runner & Service Changes

### 7.1 tools/rag/runner.py

**Before**: `run_enrich(repo_root, backend, router, start_tier, batch_size, max_spans, cooldown)`

**After**:

```python
def run_enrich(
    repo_root: Path,
    max_spans: int,
    cooldown: int,
) -> None:
    script = ...
    cmd = _python_env() + [
        str(script),
        "--repo",
        str(repo_root),
        "--max-spans",
        str(max_spans),
        "--cooldown",
        str(cooldown),
    ]
    # no backend/router/tier flags – script reads config itself
```

- `command_indexenrich` remains the same from the caller’s perspective; it just passes fewer parameters into `run_enrich`.
- Environment variables (`ENRICH_BATCH_SIZE`, etc.) remain functional and are honoured by the script via `config_enrichment` and the daemon.

### 7.2 tools/rag/service.py

- `RagService._run_repo_once` already loads `llmc.toml` as `_toml_cfg`. We reuse this:
  - `batch_size` → still taken from `[enrichment].batch_size` with `ENRICH_BATCH_SIZE` override.
  - `cooldown` → from `ENRICH_COOLDOWN` env or `[enrichment].cooldown_seconds` (new).
- Enrichment call path becomes:

```python
run_enrich(
    repo,
    max_spans=max_spans,
    cooldown=cooldown,
)
```

- Console logging updated to remove backend/router/tier in the human‑facing banner; instead we log:

```text
🤖 Enriching with configured chain (N backends, concurrency=M, cooldown=K s)
```

- On config load failure (e.g. invalid TOML, bad `ENRICH_CHAIN_JSON`), we:
  - print a short, actionable error,
  - mark the repo as “enrichment_failed” for this cycle but leave daemon running for others.

---

## 8. Docs & Examples

Update / add:

1. `scripts/rag/README.md`
   - New “Enrichment chain” section:
     - show a minimal `llmc.toml` example (single Ollama backend),
     - example with dual local models (7B primary, 14B fallback),
     - example with local 7B + gateway fallback.
   - Explain how CLI flags relate to config (e.g. `--backend ollama` filters chain entries by provider).

2. `DOCS/design/HONEY_BADGER_ENRICHMENT.md`
   - Replace the rough draft with this refined HLD/SDD summary:
     - philosophy (“Honey Badger doesn’t care”),
     - config model,
     - adapter/cascade design,
     - router & promotion mapping,
     - operational guidance (how to temporarily disable a backend, how to add Gemini as a last‑ditch fallback).

3. Small note in `DOCS/CONFIG_SAMPLES.md`
   - Add an `[enrichment]` snippet mirroring the main example.

---

## 9. SDD – File‑Level Changes & Tests

### 9.1 New: tools/rag/config_enrichment.py

**Responsibilities**

- Define dataclasses:

```python
@dataclass
class EnrichmentConfig:
    concurrency: int
    cooldown_seconds: int
    batch_size: int
    est_tokens_per_span: int
    max_retries_per_span: int
    default_tier: str
    fallback_tier: str
    chain: list[BackendConfig]
```

- Implement:

```python
def load_enrichment_config(repo_root: Path, env: Mapping[str, str] | None = None) -> EnrichmentConfig:
    ...
```

- Behaviour:
  - Load `llmc.toml` via `tomllib` (mirroring `tools.rag.service`).
  - Parse `[enrichment]` scalars, applying env overrides.
  - Parse `[[enrichment.chain]]` entries into `BackendConfig` objects.
  - If no chain present, build the default Ollama chain (7B + optional 14B fallback).
  - Validate:
    - at least one backend,
    - `provider` ∈ known set (`{"ollama", "gateway"}` for now),
    - non‑empty `name`.
  - Raise `ValueError` with human‑readable messages on bad config.

**Tests** – `tests/test_enrichment_config.py`

- `test_default_chain_when_no_toml`:
  - No `llmc.toml` → chain with one 7B Ollama backend.
- `test_parse_chain_from_toml`:
  - Example TOML with two backends → two `BackendConfig` objects parsed.
- `test_env_overrides_toml`:
  - Set `ENRICH_CONCURRENCY`, `ENRICH_COOLDOWN_SECONDS` → overrides values from TOML.
- `test_enrich_chain_json_override`:
  - Set `ENRICH_CHAIN_JSON` to a JSON array → completely replaces TOML chain.
- `test_invalid_provider_raises`:
  - `provider = "foo"` → `ValueError` mentioning the offending entry.

### 9.2 New: tools/rag/enrichment_backends.py

**Responsibilities**

- Define `BackendConfig`, `BackendError`, `BackendAdapter`, `AttemptRecord`, `BackendCascade` as per HLD.
- Provide concrete adapters:
  - `OllamaBackendAdapter` – thin wrapper over `call_via_ollama`.
  - `GatewayBackendAdapter` – thin wrapper over `call_via_gateway`.
- Include a small factory:

```python
def build_adapters(cfg: EnrichmentConfig) -> list[BackendAdapter]:
    ...
```

**Tests** – `tests/test_enrichment_cascade.py`

- `test_cascade_tries_second_on_backend_error`:
  - First fake adapter raises `BackendError`, second returns text; ensure cascade returns second and records both attempts.
- `test_cascade_raises_after_all_fail`:
  - All adapters raise `BackendError` → cascade raises with last error chained.
- `test_attempt_records_populated`:
  - Ensure `AttemptRecord` entries contain provider, model, duration, and host.

### 9.3 Refactor: scripts/qwen_enrich_batch.py

**Changes**

- Import `load_enrichment_config` and `build_adapters`.
- At startup, build `EnrichmentConfig` and `BackendCascade`.
- Replace direct calls to `call_qwen`/`call_via_ollama`/`call_via_gateway` in the main loop with a call into the cascade.
- Keep `call_via_ollama` and `call_via_gateway` helpers in this file for now but treat them as low‑level utilities used only by adapters.
- Remove or minimise hardcoded model constants from the main logic:
  - `DEFAULT_7B_MODEL` / `DEFAULT_14B_MODEL` used only inside `config_enrichment.py` to construct defaults.
- Map router tier → chain index using a helper as described in §5.

**Tests**

- Add or adjust a lightweight integration test that stubs adapters (e.g. via a test‑only adapter provider) to validate:
  - router picks the correct starting backend for short vs long spans,
  - schema failure triggers promotion (advancing chain index).

### 9.4 Runner & Service

- Update `tools/rag/runner.run_enrich` signature and call sites as described in §7.1.
- Update `tools/rag/service` enrichment call to pass only `max_spans` and `cooldown` (and rely on `llmc.toml` for everything else).

**Tests**

- Existing daemon tests that invoke `run_enrich` should still pass with minimal adjustments to expected CLI arguments.  
- Add a small CLI smoke test (non‑networked):
  - `python3 scripts/qwen_enrich_batch.py --dry-run --repo tests/data/simple_repo --max-spans 1`
  - Asserts that it reads config successfully and exits without raising.

---

## 10. Migration & Backwards Compatibility

- Existing env‑only flows (`OLLAMA_URL`, `ATHENA_OLLAMA_URL`, `ENRICH_OLLAMA_HOSTS`) continue to work:
  - If no `llmc.toml` exists, the default chain uses these envs via `resolve_ollama_host_chain`.
- Existing router policy (`router/policy.json`) is still honoured; its concept of `"default_tier"` / `"fallback_tier"` now maps onto chain indices instead of hardcoded models.
- CLI scripts and daemon commands don’t change for users:
  - `llmc-rag-service` keeps the same interface.
  - `tools/rag/runner` subcommands keep the same flags; only internal plumbing changes.
- New configuration is opt‑in:
  - If `[enrichment.chain]` is not present and no `ENRICH_CHAIN_JSON` is set, behaviour is effectively the same as today.

---

This gives you a concrete, implementable path to a configurable Honey Badger chain that:

- pulls all model/backend details out of code,
- keeps router and daemon flows intact,
- and positions you to add Gemini / OpenAI / whatever‑is‑next as simple new adapters instead of surgery in `qwen_enrich_batch.py`.
