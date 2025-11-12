# Deep Research Workflow

Last updated: 2025-11-05

## Overview
- `scripts/codex_wrap.sh` now runs a deep-research detector before routing each request. It flags high-impact prompts (architecture, compliance, major refactors, etc.) and logs a `NEEDS_DEEP_RESEARCH` event to `logs/deep_research.log`.
- When flagged, Codex prints a reminder with reasons, lightweight service quotas, and instructions for capturing findings before continuing.
- Premium routing is temporarily downgraded to the local tier unless you opt-in with `DEEP_RESEARCH_ALLOW_AUTO=1`, preventing accidental spend until manual research notes are ingested.

## Manual Intake Loop
1. Review the reminder output from Codex and perform the deep research using the suggested services.
2. Copy `research/deep_research_notes.template.md` into `research/incoming/`, rename the file (e.g., `20251105-routing-upgrade.md`), and capture findings + sources. Drop any supporting attachments (PDFs, screenshots) alongside it.
3. Run `llmc --repo /path/to/repo ingest` (or wait for the next `llmc refresh` cron tick). The command moves notes into `DOCS/RESEARCH/Deep_Research/`, stores attachments under `assets/`, and calls `rag_sync.sh` to index the new information.
4. Re-run your automation with `DEEP_RESEARCH_ALLOW_AUTO=1` once findings are in place and you want to unlock premium routing again.

## Configuration & Overrides
- Configure manual services/quotas in `config/deep_research_services.json`. Detected usage counts are tallied in `logs/deep_research_usage.jsonl`.
- Disable detection temporarily by setting `CODEX_WRAP_DISABLE_DEEP_RESEARCH=1`.
- Skip the automatic routing downgrade by exporting `DEEP_RESEARCH_ALLOW_AUTO=1` (per run).

## Logging Reference
- `logs/deep_research.log` — JSONL events documenting detections (score, reasons, keywords) **per target repo**.
- `logs/deep_research_usage.jsonl` — Rolling tally of suggestion counts per service/day.
- `logs/deep_research_ingest.log` — Movements from `research/incoming/` into the archive.
