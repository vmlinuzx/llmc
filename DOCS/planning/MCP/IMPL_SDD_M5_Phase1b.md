
# Implementation Notes — M5 Phase‑1b
## Files
- `llmc_mcp/tools/te_repo.py` — new wrappers
- `llmc_mcp/tools/test_te_repo.py` — tests

## Wiring
In your server dispatch dictionary, register the tools:
```python
from llmc_mcp.tools.te import te_run
from llmc_mcp.tools.te_repo import repo_read, rag_query

TOOL_REGISTRY["te_run"] = te_run
TOOL_REGISTRY["repo_read"] = repo_read
TOOL_REGISTRY["rag_query"] = rag_query
```
Ensure `list_tools` includes these names.

## Tests
```
PYTHONPATH=. python -m llmc_mcp.tools.test_te_repo
```
Optionally add to your smoke test after wiring:
```python
def test_list_tools_includes_te_wrappers(client):
    tools = client.list_tools()
    for name in ("te_run","repo_read","rag_query"):
        assert any(t["name"] == name for t in tools)
```
