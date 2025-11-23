# SDD – Enrichment Pipeline Observability & QoL (Phase 5)

## Goal

Add a thin observability and safety layer on top of the existing enrichment
pipeline, without changing the core semantics of span planning or backend
selection.

Specifically:

1. Provide a **per-run summary** that reports how many spans were attempted,
   succeeded, and failed, and whether the run used the config-driven
   pipeline or legacy presets.
2. Provide an optional **JSON summary output** for CI and agent tooling.
3. Add a `--dry-run-plan` mode that shows which spans *would* be enriched
   and exits before calling the LLM or writing enrichments.
4. Add two environment-variable **safety toggles** for config handling:
   - `LLMC_ENRICH_FORCE_LEGACY`
   - `LLMC_ENRICH_STRICT_CONFIG`

These are additive, low-risk changes to `scripts/qwen_enrich_batch.py` only.

## Design

### 1. Per-run Summary (Human-Facing)

At the end of `main()` after the DB is closed, we compute a summary object:

- `attempted`: number of spans we *entered* the enrichment loop for
- `succeeded`: number of spans that successfully wrote an enrichment
  (this is already tracked as `processed`)
- `failed`: number of spans that reached the failure branch
- `mode`: `"config"` if a non-empty config chain was selected,
  otherwise `"legacy"`
- `chain`: effective chain name (CLI `--chain-name` or config default)
- `backend`: effective backend (`auto`, `ollama`, or `gateway`)
- `repo_root`: stringified repo root

We print a single summary line to stderr:

```text
[enrichment] run summary: attempted=37 succeeded=35 failed=2 mode=config chain='default' backend=auto
```

The existing stdout line:

```python
print(f"Completed {processed} enrichments.")
```

is preserved for compatibility.

### 2. JSON Summary Output (Machine-Facing)

We introduce an env var:

- `LLMC_ENRICH_SUMMARY_JSON=/path/to/file.json`

When set, the same `summary` dict is written to the given path as JSON,
with `indent=2` and `sort_keys=True`. Failures to write (e.g., permission
issues) are caught and reported in verbose mode, but do not cause the run
to fail.

### 3. `--dry-run-plan` Mode

We extend `parse_args()` with:

```python
parser.add_argument(
    "--dry-run-plan",
    action="store_true",
    help="Show planned spans to enrich and exit without calling the LLM or writing enrichments.",
)
```

Behaviour in `main()`:

- After we call `enrichment_plan(...)` and verify that it returned a
  non-empty list, but **before** we enter the per-span loop, we check:

  ```python
  if args.dry_run_plan:
      print(f"[enrichment] dry-run plan (limit={this_batch}):")
      for idx, item in enumerate(plan, start=1):
          print(
              f"  {idx}. span_hash={item['span_hash']} "
              f"path={item.get('path', '<unknown>')} "
              f"lines={item.get('lines')}",
              file=sys.stderr,
          )
      return 0
  ```

- No LLM calls occur, no enrichments are written, and the DB is closed via
  the existing `finally: db.close()` block.

This is ideal for:

- Verifying that your `llmc.toml` enrichment config is selecting the expected
  spans.
- Sanity-checking which spans a large run would target before spending tokens.

### 4. Config Safety Toggles

We add two env-controlled toggles at the top of `main()`:

- `LLMC_ENRICH_FORCE_LEGACY`
  - When truthy (case-insensitive `{"1", "true", "yes", "on"}`), we **skip
    `load_enrichment_config` entirely** and operate as if no config exists.
  - In verbose mode, we log:

    ```text
    [enrichment] LLMC_ENRICH_FORCE_LEGACY is set – skipping llmc.toml config.
    ```

- `LLMC_ENRICH_STRICT_CONFIG`
  - When truthy, a config failure becomes **fatal**:
    - If `load_enrichment_config` raises `EnrichmentConfigError`, we log
      the error and `return 2` from `main()` instead of silently falling
      back to legacy presets.

The existing behaviour (fall back to presets on config error) remains the
default when `LLMC_ENRICH_STRICT_CONFIG` is not set.

### 5. Mode & Chain Detection

After config-driven CLI defaults are applied, we compute:

```python
pipeline_mode = "config" if enrichment_config is not None and selected_chain else "legacy"
effective_chain: str | None = None
if enrichment_config is not None:
    try:
        effective_chain = args.chain_name or getattr(enrichment_config, "default_chain", None)
    except Exception:
        effective_chain = args.chain_name
```

These values are used only for logging and summary output.

### 6. Counters

We add two counters at the `main()` scope:

- `attempted`: incremented once for each span we process in the per-span
  loop.
- `failed`: incremented in the failure branch where we set
  `ledger_record["result"] = "fail"`.

`processed` already counts successful enrichments; we reuse that as
`succeeded`.

## Constraints

- No schema or DB changes.
- No behavioural changes to:
  - backend selection,
  - retry logic,
  - router policy,
  - or the enrichment content/schema.
- All additions are contained within `scripts/qwen_enrich_batch.py`.
