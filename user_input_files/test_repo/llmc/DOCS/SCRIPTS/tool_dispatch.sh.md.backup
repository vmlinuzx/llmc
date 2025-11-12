# tool_dispatch.sh — LLM Tool-Call Dispatcher

Routes simple tool calls emitted by the LLM to local handlers and appends results to the model output. This keeps prompts lean while enabling on‑demand tool discovery.

- File: `llmc/scripts/tool_dispatch.sh`
- Upstream: Desk Commander MCP-lite Tool Discovery
- Consumes: STDIN (raw model text)
- Produces: STDOUT (original text + appended `[Tool Result]` section when a call is executed)

## Accepted Formats
- Fenced JSON block (preferred):
  ```json
  {"tool":"search_tools","arguments":{"query":"search term"}}
  ```
  ```json
  {"name":"describe_tool","arguments":{"name":"rg"}}
  ```
- Inline fallback (best‑effort):
  - `search_tools("search term")`
  - `describe_tool("rg")`

## Behavior
- If a recognized call is found, the dispatcher runs `llmc/scripts/tool_query.py` and appends:
  
  `---` then a `[Tool Result]` section with the command’s output.
- If no call is detected, the input is passed through unchanged.

## Examples
- Pipe JSON tool call:
  ```bash
  cat <<'EOF' | llmc/scripts/tool_dispatch.sh
  ```json
  {"tool":"search_tools","arguments":{"query":"search"}}
  ```
  EOF
  ```
- Inline fallback:
  ```bash
  printf 'Use describe_tool("rg").\n' | llmc/scripts/tool_dispatch.sh
  ```

## Integration
- `llmc/scripts/codex_wrap.sh` post‑processes model output through this dispatcher before printing/caching. No API keys required.

## Notes
- Dispatcher is intentionally strict‑ish for the JSON path and relaxed for inline patterns to keep it robust.
- Extend by adding new cases in `llmc/scripts/tool_dispatch.sh` that invoke local scripts or MCP endpoints.

