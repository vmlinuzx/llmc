# contracts_render.py — Vendor Adapters and Slices

Path
- scripts/contracts_render.py

Purpose
- Render slices from `contracts.min.json` for a chosen vendor and format.

Usage
- `python3 scripts/contracts_render.py --sidecar contracts.min.json --vendor codex --slice roles,tools --format text|json|tools`

Formats
- `text` — header + compact JSON (`@contracts:v1;vendor=codex;...\n{...}`)
- `json` — raw JSON slice
- `tools` — vendor‑specific tool declaration:
  - Codex/OpenAI: `{ tools: [ { type:"function", function:{ name, description, parameters } } ] }`
  - Claude: `{ tools: [ { name, description, input_schema } ] }`
  - Gemini: `{ tools: { function_declarations: [...] } }`

