
# Implementation Notes — M5 Phase‑1c
## Files
- `llmc_mcp/test_tools_visibility_and_metrics.py`

## Run
```
PYTHONPATH=. python -m llmc_mcp.test_tools_visibility_and_metrics
```

## Expected
- Passes if registry exposes the three TE tools.
- Skips (not fails) if `get_metrics` is not yet wired or has a non‑standard signature.
