# Enrichment Pipeline Phase 5 – Operator Guide

This document explains the observability and safety features added in
Phase 5 to `scripts/qwen_enrich_batch.py`.

## New CLI Flag: `--dry-run-plan`

Use this when you want to see **what the enrichment planner would do** without
actually calling any LLMs or writing to the database.

Example:

```bash
python scripts/qwen_enrich_batch.py --repo . --dry-run-plan --max-spans 10
```

Behaviour:

- Runs `enrichment_plan(...)` for up to `--max-spans` spans.
- Prints, to stderr:

  ```text
  [enrichment] dry-run plan (limit=10):
    1. span_hash=... path=... lines=(start, end)
    2. ...
  ```

- Exits with code `0`.
- Does **not** call the LLM or write any enrichments.

This is ideal for:

- Verifying that your `llmc.toml` enrichment config is selecting the expected
  spans.
- Sanity-checking which spans a large run would target before spending tokens.

## New Environment Variables

### `LLMC_ENRICH_FORCE_LEGACY`

When set to a truthy value (`1`, `true`, `yes`, `on`, case-insensitive),
the script behaves as if no config exists:

- `load_enrichment_config` is **not** called.
- No chains are selected.
- Legacy preset / host logic is used instead.

In verbose mode you will see:

```text
[enrichment] LLMC_ENRICH_FORCE_LEGACY is set – skipping llmc.toml config.
```

This is useful as an emergency “kill switch” when a broken config is causing
surprising behaviour in production.

### `LLMC_ENRICH_STRICT_CONFIG`

When set truthy, a config failure becomes **fatal**:

- If `load_enrichment_config` raises `EnrichmentConfigError`, the script logs
  the error and exits with code `2` instead of falling back silently to
  legacy presets.

This is ideal for CI and strict environments where you want misconfigurations
to fail fast.

### `LLMC_ENRICH_SUMMARY_JSON`

When set to a path, e.g.:

```bash
LLMC_ENRICH_SUMMARY_JSON=/tmp/enrichment_summary.json \
python scripts/qwen_enrich_batch.py --repo .
```

the script writes a JSON summary of the run:

```json
{
  "attempted": 37,
  "succeeded": 35,
  "failed": 2,
  "mode": "config",
  "chain": "default",
  "backend": "auto",
  "repo_root": "/path/to/repo"
}
```

If the file cannot be written, a verbose log message is printed but the run
still completes normally.

## Per-Run Summary Line

At the end of a run, you will now see a concise summary on stderr:

```text
[enrichment] run summary: attempted=37 succeeded=35 failed=2 mode=config chain='default' backend=auto
```

The existing stdout line:

```text
Completed 35 enrichments.
```

remains for backwards compatibility.

You can safely grep for `"[enrichment] run summary:"` in logs or use
`LLMC_ENRICH_SUMMARY_JSON` for machine-readable post-processing.
