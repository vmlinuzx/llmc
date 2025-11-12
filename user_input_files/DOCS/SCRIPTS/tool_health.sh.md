# tool_health.sh — Local Tool Capability Probe

Path
- scripts/tool_health.sh

Purpose
- Inspect declared tools in `.codex/tools.json`, detect their presence/versions via `verify` commands, and write two artifacts: a detailed JSON report and a compact `CLAUDE_TOOLCAPS` export line for downstream wrappers.

Usage
- `scripts/tool_health.sh` (optional `TOOLS_MANIFEST=/path/to/tools.json`)

Outputs
- `.codex/state/tools.json` — `{ status: 'ok', detected: { cli_tools[], mcp_servers[], models[] } }`
- `.codex/state/tools.env` — `export CLAUDE_TOOLCAPS="bash_exec,fs_rw,ollama:code,gemini:on,..."`

Notes
- Degrades gracefully when `jq` or the manifest is missing.

