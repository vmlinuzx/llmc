
# Implementation SDD – Config‑Driven Enrichment Chains (Phase 5)

**Status:** Ready for implementation  
**Scope:** Make enrichment model/backend selection driven by `llmc.toml` + env via `config_enrichment`, and wire it into `qwen_enrich_batch.py` using the existing `BackendCascade` abstraction.

---

## 1. Tasks Overview

1. Implement and test `tools/rag/config_enrichment.py` as the enrichment config loader.
2. Integrate `EnrichmentConfig` into `scripts/qwen_enrich_batch.py`:
   - extend CLI,
   - load config,
   - update `_build_cascade_for_attempt` to use chains where available.
3. Optionally adjust `tools/rag/runner.py` / `tools/rag/service.py` to pass `--chain-name`.
4. Update docs to describe the chain‑driven model and how to configure it.

---

## 2. Detailed Tasks

### Task 1 – Implement `tools/rag/config_enrichment.py`

**Goal:** Introduce a dedicated enrichment configuration loader/validator that understands `[enrichment]` and `[[enrichment.chain]]` in `llmc.toml`, supports env overrides, and returns a typed `EnrichmentConfig`.

**Steps:**

1. **Create the module**

   - Path: `tools/rag/config_enrichment.py`
   - Add standard imports: `dataclasses`, `Path`, `Mapping`, `typing`, `os`, and a TOML parser that matches the repo’s conventions (`tomllib` in stdlib for Python ≥3.11, or a third‑party lib already used elsewhere in LLMC).

2. **Define types**

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


   class EnrichmentConfigError(ValueError):
       pass
   ```

3. **Implement `load_enrichment_config`**

   Signature:

   ```python
   def load_enrichment_config(
       repo_root: Path,
       *,
       toml_path: Path | None = None,
       env: Mapping[str, str] | None = None,
   ) -> EnrichmentConfig:
       ...
   ```

   Behaviour:

   - Resolve `env = os.environ` if not provided.
   - Determine TOML path:
     - Use `toml_path` if provided.
     - Else use `repo_root / "llmc.toml"` if it exists.
     - Else treat as “no config” and return default config (Step 5).
   - Parse TOML and read `[enrichment]` and `[[enrichment.chain]]` tables.
   - Extract raw values:
     - `default_chain`, `concurrency`, `cooldown_seconds`.
     - For each `[[enrichment.chain]]`:
       - `chain`, `name`, `provider`, `model`, `url`, `routing_tier`, `timeout_seconds`, `enabled`, `options`.
   - Apply env overrides:
     - If `ENRICH_CONCURRENCY` set, override `concurrency`.
     - If `ENRICH_COOLDOWN_SECONDS` set, override `cooldown_seconds`.
     - If `ENRICH_CHAIN_JSON` set:
       - Parse JSON; replace/augment the chain definitions from TOML for the relevant chain(s).
       - On parse/validation failure: log/raise `EnrichmentConfigError` as appropriate.
   - Validate:
     - Each entry must have `name` and `provider`.
     - `provider` in allowed set: for now `{"ollama", "gateway", "gemini"}`.
     - If `routing_tier` is not `None`, it must be in `{"7b", "14b", "nano"}`.
     - At least one enabled entry in `default_chain` (or effective default chain).
   - Build and return `EnrichmentConfig`.

4. **Implement `select_chain`**

   ```python
   def select_chain(
       config: EnrichmentConfig,
       chain_name: str | None,
   ) -> list[EnrichmentBackendSpec]:
       ...
   ```

   - Determine effective chain name:
     - If `chain_name` is not None: use it.
     - Else use `config.default_chain`.
   - Look up the chain in `config.chains`.
   - Filter by `enabled`.
   - If no enabled entries:
     - Raise `EnrichmentConfigError(f"No enabled entries for chain {chain_name!r}")`.

5. **Implement `filter_chain_for_tier`**

   ```python
   def filter_chain_for_tier(
       chain: list[EnrichmentBackendSpec],
       routing_tier: str,
   ) -> list[EnrichmentBackendSpec]:
       ...
   ```

   Design choice for Phase 5:

   - Include entries where:
     - `spec.routing_tier == routing_tier`, or
     - `spec.routing_tier is None` **and** `routing_tier == "7b"` (treat no tier as 7B primary).
   - Sorted by original order in `chain`.

6. **Default config (no TOML case)**

   - If TOML is missing entirely:
     - Return an `EnrichmentConfig` that models the current behaviour:
       - Single chain `"default"`.
       - One `EnrichmentBackendSpec` for Ollama tier `"7b"` (`provider="ollama"`, `routing_tier="7b"`, `url=ATHENA_OLLAMA_URL or "http://localhost:11434"`).
       - `concurrency = 1`, `cooldown_seconds = 0`.

7. **Unit tests in `tests/test_enrichment_config.py`**

   - Cover:
     - Parsing valid TOML with one chain.
     - Multiple chains and tier filters.
     - Env overrides for `ENRICH_CONCURRENCY`, `ENRICH_COOLDOWN_SECONDS`.
     - Error cases (unknown provider, bad tier, missing entries).

---

### Task 2 – Integrate Config with `scripts/qwen_enrich_batch.py`

**Goal:** Make `qwen_enrich_batch` use `EnrichmentConfig` to build its per‑attempt `BackendCascade`, while preserving fallback behaviour.

**Steps:**

1. **Add imports**

   At the top of `scripts/qwen_enrich_batch.py` add:

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

2. **Extend CLI arguments**

   In `parse_args()` add:

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

   - Do **not** remove existing `--backend`, `--api`, `--local` flags in this phase.

3. **Load config in `main()`**

   Near the top of `main()` (after parsing args and computing `repo_root`):

   ```python
   enrichment_config: EnrichmentConfig | None = None
   selected_chain: list[EnrichmentBackendSpec] | None = None

   try:
       enrichment_config = load_enrichment_config(
           repo_root=repo_root,
           toml_path=args.chain_config,
       )
   except EnrichmentConfigError as exc:
       print(f"[enrichment] config error: {exc} – falling back to presets.", file=sys.stderr)
       enrichment_config = None

   if enrichment_config is not None:
       try:
           selected_chain = select_chain(enrichment_config, args.chain_name)
       except EnrichmentConfigError as exc:
           print(f"[enrichment] chain selection error: {exc} – falling back to presets.", file=sys.stderr)
           selected_chain = None
   ```

   - Pass `enrichment_config` and `selected_chain` into `_build_cascade_for_attempt` in the main attempt loop.

4. **Update `_build_cascade_for_attempt`**

   Change signature to:

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
   ```

   Implementation:

   - If `enrichment_config` and `selected_chain` are not `None`:
     - Compute:

       ```python
       tier_chain = filter_chain_for_tier(list(selected_chain), tier_for_attempt)
       ```

     - If `tier_chain` is non‑empty:
       - For each `spec` in `tier_chain`, map to the correct adapter:
         - `spec.provider == "ollama"` → `_OllamaBackendAdapter` with:
           - `host_url = spec.url or env default or host chain entry`,
           - `tier_preset` based on `tier_for_attempt` / `PRESET_CACHE`,
           - overrides from `spec.options` and `spec.model`.
         - `spec.provider in {"gateway", "gemini"}` → `_GatewayBackendAdapter` with model hint from `spec.model`.
       - Build `BackendCascade(adapters=adapters)` and return it along with computed `preset_key`, `tier_preset`, `host_label`, `host_url`, `selected_backend`, `chain_name_used`.
     - If `tier_chain` is empty, fall through to legacy logic.

   - If `enrichment_config` or `selected_chain` is `None`:
     - Use the existing Phase‑4 logic (single adapter derived from `tier_for_attempt` and `backend` flag).

5. **Plumb extra return value into attempt loop**

   In the main attempt loop where `_build_cascade_for_attempt` is called:

   ```python
   cascade, preset_key, tier_preset, host_label, host_url, selected_backend, chain_name_used = _build_cascade_for_attempt(
       backend=backend,
       tier_for_attempt=tier_for_attempt,
       repo_root=repo_root,
       args=args,
       ollama_host_chain=ollama_host_chain,
       current_host_idx=current_host_idx,
       host_chain_count=host_chain_count,
       enrichment_config=enrichment_config,
       selected_chain=selected_chain,
   )
   ```

6. **Metrics / ledger additions**

   When appending attempt records and final ledger entries, add:

   - `chain_name`: `chain_name_used`.
   - `backend_name`: `spec.name` for the backend that succeeded (this can be surfaced via meta, or by enriching the meta dict in the adapters).

   Keep these fields optional (only present when config is in use).

7. **Integration tests**

   - Add a new test file `tests/test_enrichment_chain_integration.py`:
     - Use a temporary TOML to create a config with:
       - one Ollama entry (`routing_tier = "7b"`),
       - one gateway entry (`routing_tier = "14b"`).
     - Patch `load_enrichment_config` / `select_chain` or call them directly with that TOML.
     - Call `_build_cascade_for_attempt` with `tier_for_attempt="7b"`, then `"14b"`.
     - Assert that `cascade.adapters` contains the expected adapter types in the correct order.

---

### Task 3 – Runner / Service (Optional, Thin)

If `tools/rag/runner.py` or `tools/rag/service.py` currently passes `--backend` directly to `qwen_enrich_batch.py`, consider:

- Keeping existing behaviour for now for backwards compatibility.
- Adding awareness of `--chain-name` when invoking the script, so ops can use chains at the orchestration level without editing code.

Full re‑design of runner/service is out‑of‑scope for this phase.

---

### Task 4 – Documentation

1. **Update script README**

   - In `scripts/rag/README.md` (or equivalent) document:

     - The `[enrichment]` and `[[enrichment.chain]]` TOML schema.
     - Example configs for:
       - single Athena chain,
       - dual local models with Gemini fallback,
       - gateway‑only chain.
     - How to use `--chain-name` and `--chain-config`.

2. **HONEY_BADGER_ENRICHMENT / design docs**

   - Add a “Config‑Driven Chains” section that explains:

     - How router tiers (`"7b"`, `"14b"`, `"nano"`) map to `routing_tier` in config.
     - How failover occurs within a chain (order) vs across tiers (router logic).

---

## 3. Acceptance Criteria

- With a valid `[enrichment]` config, `qwen_enrich_batch`:

  - Uses the configured chain(s) and per‑entry provider/model/URL for enrichment.
  - Respects router tier promotion and host failover semantics as before.
  - Records which chain + backend entry was used for each attempt.

- With **no** config or an invalid config, `qwen_enrich_batch`:

  - Falls back cleanly to the existing PRESET/host‑chain behaviour.
  - Logs a clear warning about the config problem.

- Unit tests for `config_enrichment` and integration tests for chain selection pass.
- Existing enrichment tests continue to pass or are updated with clear reasoning.
