# LLMC Contracts Sidecar v1 — System Design & Implementation

## Executive Summary
Keep `CONTRACTS.md` as the human source of truth. Generate a deterministic, minified, sliceable sidecar `contracts.min.json`
for ingestion. At runtime, the gateway requests only the slices it needs (e.g., `roles,tools`), rendered into the correct
vendor dialect (Claude, Gemini, OpenAI/Codex). Expect 50–80% token savings with zero vendor drift.

## Architecture
CONTRACTS.md --(contracts_build.py)--> contracts.min.json (+ contracts.sidecar.sha256)
                                     \-(contracts_validate.py)
Runtime: contracts_render.py --vendor {codex|claude|gemini} --slice roles,tools --format {text|json|tools}
Gateway prepends the compact block to system/context. Escape hatch: CONTRACTS_USE_FULL=1.

## Sidecar Schema (v1)
- v (int) schema version
- roles[]: { id, sc (scope), cap[], lim[] }
- tools[]: { id, in (JSON schema), out?, cost? }
- flows[]: { id, steps[], ent?, ok? }
- pol[]:   { id, rule, sev [0..3] }
- gloss[]: { term, canon, aka[] }
- idents[]: identifiers extracted from prose (filenames, env vars, paths)

## Build Pipeline
- `python3 scripts/contracts_build.py --in CONTRACTS.md --out contracts.min.json`
  - parses sections (## Roles/Workflows/Policies/Glossary)
  - supports bullet key: value or fenced ```json blocks under ### <id>
  - extracts idents and writes minified JSON with stable key order
  - hydrates `tools` from `.codex/tools.json` (`llm_tools` array) and records `tool_manifest` path
  - writes contracts.sidecar.sha256 (sha256 of bytes)
- `python3 scripts/contracts_validate.py` checks checksum drift
- `scripts/contracts_precommit.sh` runs both

## Rendering Adapters
`python3 scripts/contracts_render.py --vendor codex --slice roles,tools --format tools|text|json`
- text: header + minified JSON slice (`@contracts:v1;vendor=codex;slice=roles,tools\n{...}`)
- tools: proper envelope per vendor (OpenAI tools[], Anthropic tools[], Gemini function_declarations)

## Gateway Integration
Env flags:
- CONTRACTS_SIDECAR=contracts.min.json
- CONTRACTS_VENDOR=codex|claude|gemini
- CONTRACTS_SLICES=roles,tools
- CONTRACTS_USE_FULL=0  (set 1 to bypass sidecar)

Insert `PATCHES/LLM_GATEWAY_CONTRACTS_HOOK.txt` after your "// BUILD PROMPT START" to fetch and prepend the sidecar block.

## Observability / QA
- Build log: .llmc/logs/contracts_build.jsonl
- Validate log: .llmc/logs/contracts_validate.jsonl
- Golden facts test (CI): verify a few known answers match sidecar vs MD.

## Rollout
1) Shadow: generate and render slices alongside full prose (don’t use).  
2) Partial: feed roles+tools from sidecar; leave flows as prose.  
3) Full: route all vendors to sidecar slices; tools from sidecar.  
Keep CONTRACTS_USE_FULL=1 escape hatch.

## Acceptance
- ≥50% token reduction across ingest prompts; no behavior regressions in golden tests.
- CI blocks drift/schema errors.
