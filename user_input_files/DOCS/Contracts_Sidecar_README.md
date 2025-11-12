# LLMC Contracts Sidecar v1
Generate a deterministic, token-efficient sidecar from CONTRACTS.md and render vendor slices at runtime.

## Build
python3 scripts/contracts_build.py --in CONTRACTS.md --out contracts.min.json
python3 scripts/contracts_validate.py

## Runtime (gateway)
node -e "console.log(require('./node/contracts_loader').renderSlice({}))"

## Env
CONTRACTS_SIDECAR=contracts.min.json
CONTRACTS_VENDOR=codex   # claude|gemini
CONTRACTS_SLICES=roles,tools
CONTRACTS_USE_FULL=0

Tool definitions (CLI inventory, MCP servers, callable LLM helpers) live in `.codex/tools.json`. The contract and sidecar reference that manifest; update the JSON whenever tools change.

See DOCS/SDD_Contracts_Sidecar_v1.md for full design.
