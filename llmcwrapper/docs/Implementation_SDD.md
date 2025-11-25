# Implementation SDD: llmcwrapper
**Date:** 2025-11-12 19:46  
**Status:** Implemented (phase 1)

## Modules
- `llmcwrapper.adapter` — resolve config → invariants → provider dispatch → telemetry/cost
- `llmcwrapper.config` — TOML load/merge, overlays, one-offs, snapshot
- `llmcwrapper.providers` — drivers + factory
- `llmcwrapper.telemetry` — events.jsonl per run (corr_id)
- `llmcwrapper.capabilities` — per-provider feature flags
- `llmcwrapper.costs` — configurable pricing
- `llmcwrapper.rag_client` — HEAD health check

## CLIs
- `llmc-yolo` / `llmc-rag` — main entrypoints (+ `--shadow-profile`)
- `llmc-doctor` — health/config checks
- `llmc-profile` — show/set profiles

## Invariants
- yolo ⇒ no tools, no RAG
- rag ⇒ RAG enabled + reachable (unless --force)

## Telemetry
- `.llmc/runs/<corr_id>/resolved-config.json`
- `.llmc/runs/<corr_id>/events.jsonl` (start, provider_request_meta, cost_estimate, dry_run)

## Next
- Real MiniMax HTTP, streaming shim, tool normalization, record/replay fixtures.
