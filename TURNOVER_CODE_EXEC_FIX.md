# Turnover: Code Execution Mode Bug Fix

**Date:** 2024-12-01  
**Issue:** `_call_tool` injection bug preventing code execution mode from working  
**Status:** FIXED, ready for activation  

---

## Context

LLMC implements the Anthropic "Code Mode" pattern for MCP tools:
- Reference: https://www.anthropic.com/engineering/code-execution-with-mcp
- Goal: Reduce 23 MCP tools → 3 bootstrap tools (98% token reduction)
- Bootstrap tools: `list_dir`, `read_file`, `execute_code`
- All other tools become importable Python stubs in `.llmc/stubs/`

The feature was fully implemented but disabled due to a bug.

## The Bug

Generated stubs imported `_call_tool` from the module:

```python
# BAD - gets the NotImplementedError placeholder version
from llmc_mcp.tools.code_exec import _call_tool

def rag_search(query: str) -> dict:
    return _call_tool("rag_search", locals())
```

But `execute_code()` only injected the real `tool_caller` into the exec namespace, not the module. When stubs were imported, they got the placeholder that raises `NotImplementedError`.

## The Fix

Three changes to `llmc_mcp/tools/code_exec.py`:

1. **Stub template** - Remove the import, rely on builtins injection:
```python
# _call_tool is injected into builtins by execute_code() at runtime.
# Do NOT import it - that gets the NotImplementedError placeholder.
```

2. **execute_code()** - Inject into builtins so imports can find it:
```python
import builtins
_original_call_tool = getattr(builtins, '_call_tool', None)
builtins._call_tool = tool_caller
```

3. **Cleanup** - Restore builtins in finally block to avoid pollution

## Files Changed

- `llmc_mcp/tools/code_exec.py` - Bug fix (3 surgical edits)
- `llmc_mcp/tools/test_code_exec.py` - NEW: 8 tests including regression test

---

## Testing

### Run the test suite

```bash
cd ~/src/llmc

# Run code_exec tests specifically
python3 -m pytest llmc_mcp/tools/test_code_exec.py -v

# Run all MCP tool tests
python3 -m pytest llmc_mcp/tools/test_*.py -v

# Expected: 30 passed
```

### Critical test to watch

`test_import_stub_calls_injected_tool` - This is the regression test for the bug:
- Generates a stub
- Executes code that imports and calls the stub
- Verifies the injected `tool_caller` was actually invoked
- If this fails, the bug is back

### Manual integration test

```bash
# 1. Enable code execution mode
sed -i 's/enabled = false/enabled = true/' llmc.toml

# 2. Verify config change
grep -A2 '\[mcp.code_execution\]' llmc.toml

# 3. Start server in debug mode to see stub generation
python3 -m llmc_mcp.server --log-level debug 2>&1 | head -50

# Look for:
# - "Code execution mode: generating stubs in .llmc/stubs"
# - "Generated N stub files"
# - "Code execution mode: 5 bootstrap tools registered"

# 4. Check generated stubs
ls -la .llmc/stubs/
cat .llmc/stubs/rag_search.py
# Verify: NO "from llmc_mcp.tools.code_exec import _call_tool" line

# 5. Revert if needed
sed -i 's/enabled = true/enabled = false/' llmc.toml
```

### Claude Desktop integration test

1. Edit `llmc.toml`: set `[mcp.code_execution] enabled = true`
2. Restart Claude Desktop
3. Start a new conversation
4. Ask Claude: "List the tools you have available from LLMC"
5. Expected: Only 5 tools (health, list_tools, list_dir, read_file, execute_code)
6. Ask Claude: "Use execute_code to search the RAG index for 'router'"
7. Claude should write Python code that imports from stubs and executes

---

## Activation Checklist

- [x] Bug fixed in code_exec.py
- [x] Tests written and passing (8 new tests)
- [x] Full test suite passes (30 tests)
- [ ] Enable in config: `[mcp.code_execution] enabled = true`
- [ ] Restart Claude Desktop
- [ ] Verify stub generation in logs
- [ ] Test end-to-end with Claude

## Rollback

If issues arise:
```bash
# Disable code execution mode
sed -i 's/enabled = true/enabled = false/' llmc.toml
# Restart Claude Desktop
```

Classic mode (23 tools) will resume.

---

## Token Savings Estimate

| Mode | Tools in Context | Est. Tokens |
|------|------------------|-------------|
| Classic | 23 full definitions | ~2,000 |
| Code Exec | 5 bootstrap + stubs on-demand | ~500 |

**Savings: ~75% reduction per turn**

For a 10-turn conversation, that's ~15,000 tokens saved.
