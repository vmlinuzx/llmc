# contracts_build.py — Build Sidecar from CONTRACTS.md

Path
- scripts/contracts_build.py

Purpose
- Parse `CONTRACTS.md` into a deterministic, minified, sliceable `contracts.min.json` with extracted roles, tools, flows, policies, glossary, and identifiers. Optionally hydrate `tools` from `.codex/tools.json`.

Usage
- `python3 scripts/contracts_build.py --in CONTRACTS.md --out contracts.min.json [--version 1]`

Outputs
- `contracts.min.json` and `contracts.sidecar.sha256`; logs to `.llmc/logs/contracts_build.jsonl`.

Notes
- Recognizes `### <id>` subsections, `- key: value` bullets, and fenced ```json blocks.

