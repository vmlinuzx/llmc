# tool_query.py — Manifest-backed Tool Discovery

Minimal MCP‑lite helper that searches and describes tools declared in `.codex/tools.json`.

- File: `scripts/tool_query.py`
- Source of truth: `.codex/tools.json` (`cli_tools`, `llm_tools`)
- Outputs: human‑readable lines for search, Markdown summary for describe

## Usage
```bash
python3 scripts/tool_query.py search "search term"
python3 scripts/tool_query.py describe rg
```

## Behavior
- `search <query>`: case‑insensitive substring match against `id`, `name`, `description`, `capabilities[]`.
  - Output: lines like `id — Name: description`.
- `describe <name>`: exact match on `id` or `name`.
  - Output: Markdown with name, ID, capabilities, min version, and optional usage.

## Integration
- Advertised to the LLM via `.codex/tools.json` entries:
  - `search_tools` with schema `{ query: string }`
  - `describe_tool` with schema `{ name: string }`
- `scripts/tool_dispatch.sh` calls this script when the LLM emits a tool call.

## Notes
- Keep `.codex/tools.json` authoritative; this script does no network I/O.
- Extend fields or matching as your manifest evolves.

