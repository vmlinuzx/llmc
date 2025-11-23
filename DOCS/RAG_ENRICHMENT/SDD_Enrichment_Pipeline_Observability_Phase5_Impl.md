# Implementation Notes – Phase 5 Observability & QoL

## File Touched

- `scripts/qwen_enrich_batch.py` (single unified diff patch)

## Argument Changes

In `parse_args()` we insert:

```python
parser.add_argument(
    "--dry-run-plan",
    action="store_true",
    help="Show planned spans to enrich and exit without calling the LLM or writing enrichments.",
)
```

directly after the existing `--dry-run` flag.

## `main()` Changes

1. **Environment toggles and summary path**

At the top of `main()` after parsing args and ensuring `repo_root`:

```python
force_legacy = os.environ.get("LLMC_ENRICH_FORCE_LEGACY", "").lower() in _TRUTHY
strict_config = os.environ.get("LLMC_ENRICH_STRICT_CONFIG", "").lower() in _TRUTHY
summary_json_path = os.environ.get("LLMC_ENRICH_SUMMARY_JSON")
```

2. **Config loading with safety toggles**

We replace the existing `load_enrichment_config` / `select_chain` block with:

```python
enrichment_config: EnrichmentConfig | None = None
selected_chain: Sequence[EnrichmentBackendSpec] | None = None
if not force_legacy:
    try:
        enrichment_config = load_enrichment_config(
            repo_root=repo_root,
        )
        selected_chain = select_chain(enrichment_config, args.chain_name)
    except EnrichmentConfigError as exc:
        print(
            f"[enrichment] config error: {exc} – falling back to presets.",
            file=sys.stderr,
        )
        if strict_config:
            return 2
        enrichment_config = None
        selected_chain = None
else:
    if args.verbose:
        print(
            "[enrichment] LLMC_ENRICH_FORCE_LEGACY is set – skipping llmc.toml config.",
            file=sys.stderr,
        )
```

The existing empty-chain fallback remains as-is:

```python
if enrichment_config is not None and not selected_chain:
    ...
    enrichment_config = None
    selected_chain = None
```

3. **Pipeline mode and chain detection**

After config-driven defaults and before backend selection:

```python
pipeline_mode = "config" if enrichment_config is not None and selected_chain else "legacy"
effective_chain: str | None = None
if enrichment_config is not None:
    try:
        effective_chain = args.chain_name or getattr(enrichment_config, "default_chain", None)
    except Exception:
        effective_chain = args.chain_name
```

4. **Counters and dry-run-plan logic**

Near the DB setup:

```python
db_file = index_path_for_write(repo_root)
db = Database(db_file)
processed = 0
attempted = 0
failed = 0
```

And in the main loop:

```python
while True:
    ...
    plan = enrichment_plan(db, repo_root, limit=this_batch, cooldown_seconds=args.cooldown)
    if not plan:
        print("No more spans pending enrichment.")
        break

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

    total_spans = len(plan)
    for idx, item in enumerate(plan, start=1):
        attempted += 1
        ...
```

And in the failure branch:

```python
else:
    ledger_record["result"] = "fail"
    failed += 1
    failure_reason = failure_info[0] if failure_info else "unknown"
    ledger_record["reason"] = failure_reason
    ...
```

5. **Summary + JSON output**

After the `try/finally` block that closes the DB:

```python
summary = {
    "attempted": attempted,
    "succeeded": processed,
    "failed": failed,
    "mode": pipeline_mode,
    "chain": effective_chain,
    "backend": backend,
    "repo_root": str(repo_root),
}
print(
    f"[enrichment] run summary: attempted={summary['attempted']} "
    f"succeeded={summary['succeeded']} failed={summary['failed']} "
    f"mode={summary['mode']} chain={summary['chain'] or '-'} backend={summary['backend']}",
    file=sys.stderr,
)
if summary_json_path:
    try:
        with open(summary_json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, sort_keys=True)
    except OSError as exc:
        if args.verbose:
            print(
                f"[enrichment] failed to write summary JSON to {summary_json_path}: {exc}",
                file=sys.stderr,
            )
```

We then retain the existing:

```python
print(f"Completed {processed} enrichments.")
return 0
```

## Diff Size

The unified diff for `scripts/qwen_enrich_batch.py` contains ~80 added lines and
only 9 deletions, reflecting a targeted, additive change.

## Test Plan

1. **Unit/Integration tests**

Run:

```bash
pytest tests/test_enrichment_integration.py -vv
pytest tests/test_enrichment_batch.py -vv
pytest tests -q
```

2. **Manual smoke tests**

- Normal run with config:

  ```bash
  python scripts/qwen_enrich_batch.py --repo . --verbose
  ```

  Confirm:
  - Backend selection and existing logs still appear.
  - A final summary line is printed.
  - `Completed N enrichments.` still appears.

- Dry-run plan:

  ```bash
  python scripts/qwen_enrich_batch.py --repo . --dry-run-plan --max-spans 5
  ```

  Confirm:
  - Plan is printed (span hashes, paths, lines).
  - No enrichments are written.
  - Exit code is 0.

- Strict config:

  ```bash
  LLMC_ENRICH_STRICT_CONFIG=1 python scripts/qwen_enrich_batch.py --repo .
  ```

  With a deliberately broken config, confirm:
  - Config error is logged.
  - Exit code is 2.

- Force legacy:

  ```bash
  LLMC_ENRICH_FORCE_LEGACY=1 python scripts/qwen_enrich_batch.py --repo . --verbose
  ```

  Confirm:
  - LLMC_ENRICH_FORCE_LEGACY log line appears.
  - Run proceeds using legacy presets.
