# Phase 1.Z: MCP RLM Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate the Recursive Loop Manager (RLM) into the MCP server as a tool, enabling external agents to trigger and manage recursive optimization loops.

**Architecture:**
The RLM will be exposed as an MCP tool (`run_rlm`). The configuration will be managed via `llmc_mcp/config.py`. The tool logic will reside in `llmc_mcp/tools/rlm.py`, wrapping the core `llmc.rlm` functionality. The server (`llmc_mcp/server.py`) will register this new tool.

**Tech Stack:** Python, MCP (Model Context Protocol), Pytest.

---

### Task 1: Add MCP Config Surface `[mcp.rlm]`

**Files:**
- Modify: `llmc_mcp/config.py`
- Test: `tests/mcp/test_config.py` (create if needed, or add to existing config test)

**Step 1: Write the failing test**

Create `tests/mcp/test_rlm_config.py`:
```python
from llmc_mcp.config import MCPServerConfig

def test_rlm_config_defaults():
    config = MCPServerConfig()
    assert config.rlm.enabled is False
    assert config.rlm.max_loops == 5
    assert config.rlm.timeout == 300
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/mcp/test_rlm_config.py -v`
Expected: FAIL (AttributeError: 'MCPServerConfig' object has no attribute 'rlm')

**Step 3: Implement Config Changes**

Modify `llmc_mcp/config.py`:
- Add `RLMConfig` class (pydantic model).
- Add `rlm: RLMConfig = Field(default_factory=RLMConfig)` to `MCPServerConfig`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/mcp/test_rlm_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add llmc_mcp/config.py tests/mcp/test_rlm_config.py
git commit -m "feat(mcp): add RLM configuration to MCPServerConfig"
```

---

### Task 2: Implement Tool Logic in `llmc_mcp/tools/rlm.py`

**Files:**
- Create: `llmc_mcp/tools/rlm.py`
- Test: `tests/mcp/test_tool_rlm.py`

**Step 1: Write the failing test**

Create `tests/mcp/test_tool_rlm.py`:
```python
import pytest
from llmc_mcp.tools.rlm import RLMTool
from llmc_mcp.config import RLMConfig

def test_rlm_tool_initialization():
    config = RLMConfig(enabled=True)
    tool = RLMTool(config)
    assert tool.name == "run_rlm"
    assert "recursive" in tool.description.lower()

@pytest.mark.asyncio
async def test_rlm_tool_execution_disabled():
    config = RLMConfig(enabled=False)
    tool = RLMTool(config)
    with pytest.raises(Exception, match="RLM is disabled"):
        await tool.run({"goal": "test"})
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/mcp/test_tool_rlm.py -v`
Expected: FAIL (ImportError)

**Step 3: Implement Tool Logic**

Create `llmc_mcp/tools/rlm.py`:
- Define `RLMTool` class.
- Implement `__init__` and `run` methods.
- `run` should call into `llmc.rlm` (mocked for now if needed, or real integration).
- Ensure it respects `enabled` config.

**Step 4: Run test to verify it passes**

Run: `pytest tests/mcp/test_tool_rlm.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add llmc_mcp/tools/rlm.py tests/mcp/test_tool_rlm.py
git commit -m "feat(mcp): implement RLM tool logic"
```

---

### Task 3: Register MCP Tool Definition in `llmc_mcp/server.py`

**Files:**
- Modify: `llmc_mcp/server.py`
- Test: `tests/mcp/test_server_rlm_registration.py`

**Step 1: Write the failing test**

Create `tests/mcp/test_server_rlm_registration.py`:
```python
import pytest
from llmc_mcp.server import create_mcp_server
from llmc_mcp.config import MCPServerConfig

@pytest.mark.asyncio
async def test_rlm_tool_registered():
    config = MCPServerConfig()
    config.rlm.enabled = True
    server = create_mcp_server(config)
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "run_rlm" in tool_names
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/mcp/test_server_rlm_registration.py -v`
Expected: FAIL ("run_rlm" not found in tools)

**Step 3: Register Tool**

Modify `llmc_mcp/server.py`:
- Import `RLMTool`.
- Initialize `RLMTool` with config.
- Add to `list_tools` and `call_tool` handlers.

**Step 4: Run test to verify it passes**

Run: `pytest tests/mcp/test_server_rlm_registration.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add llmc_mcp/server.py tests/mcp/test_server_rlm_registration.py
git commit -m "feat(mcp): register RLM tool in server"
```

---

### Task 4: Verification

**Files:**
- Run existing tests: `tests/rlm/`, `tests/mcp/`

**Step 1: Run RLM tests**
Run: `pytest tests/rlm/ -v --allow-network`

**Step 2: Run MCP tests**
Run: `pytest tests/mcp/ -v`

**Step 3: Fix any regressions**
(If any failures, fix them and commit)

---

### Task 5: Documentation (Phase 1.AA)

**Files:**
- Modify: `docs/user_guide.md` (or similar), `docs/api_reference.md`

**Step 1: Update User Guide**
- Add section on using `run_rlm` via MCP.
- Explain configuration options.

**Step 2: Commit**
```bash
git add docs/
git commit -m "docs: add RLM MCP tool documentation"
```
