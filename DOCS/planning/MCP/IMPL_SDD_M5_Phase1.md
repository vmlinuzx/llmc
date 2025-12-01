
# Implementation Notes — M5 Phase‑1
## Files
- `llmc_mcp/tools/te.py` — new TE wrapper tool
- `llmc_mcp/tools/test_te.py` — tests (monkeypatch subprocess)
- (server wiring) — register `"te_run"` pointing to `llmc_mcp.tools.te:te_run`

## Steps
1. Drop files into repo preserving paths.
2. Wire server dispatch dict:
   ```python
   # server.py (concept)
   from llmc_mcp.tools.te import te_run
   TOOL_REGISTRY["te_run"] = te_run
   ```
3. Run tests:
   ```bash
   PYTHONPATH=. python -m llmc_mcp.tools.test_te
   ```

## Follow‑ups (Phase‑1b)
- Add `repo_read` and `rag_query` thin wrappers.
- Add `list_tools` smoke test in `test_smoke.py`.
