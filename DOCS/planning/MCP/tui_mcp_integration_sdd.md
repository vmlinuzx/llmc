# MCP-Native TUI Integration — System Design Document

**Created:** 2025-12-02  
**Status:** Design Document  
**Priority:** P1 - Post-MVP Enhancement  
**Owner:** Dave

---

## Executive Summary

Replace the current "AGENTS.md blathering" pattern in TUI wrappers (`gmaw.sh`, `claude_minimax_rag_wrapper.sh`, `codex_rag_wrapper.sh`) with **MCP-native tool access**. This will:

- **Reduce token usage by 90%+** (eliminate 160-line AGENTS.md dumps)
- **Provide fresher context** (just-in-time RAG queries vs. static file dumps)
- **Unify tool access** (same tools for TUIs, Claude Desktop, ChatGPT, etc.)
- **Enable code execution mode** (LLMs write Python to query system state)

---

## Problem Statement

### Current State (The "Blathering" Problem)

All three TUI wrappers follow the same pattern:

```bash
# From claude_minimax_rag_wrapper.sh:207
build_preamble() {
  # ... 
  [ -f "$agents_md" ] && read_top "$agents_md" 160    # 📊 ~8KB
  [ -f "$contracts_md" ] && read_top "$contracts_md" 160  # 📊 ~6KB
  [ -f "$history_md" ] && read_top "$history_md" 80      # 📊 ~3KB
  # Total: ~17KB of static context per session
}
```

**Problems:**
1. **Token waste**: 160 lines of AGENTS.md + 160 lines of CONTRACTS.md = **~17KB** upfront
2. **Stale data**: Context is from file read, not live system state
3. **No selectivity**: LLM gets everything, even irrelevant sections
4. **Maintenance burden**: Three separate wrappers doing the same thing
5. **No tool access**: LLMs can't query RAG, inspect files, or check stats

### Desired State (MCP-Native)

```bash
build_preamble() {
  cat <<'EOF'
You have access to LLMC via MCP tools. Use them for context.

Available tools:
- rag_search(query) - Find code/docs
- inspect(path|symbol) - Deep dive with graph context
- rag_where_used(symbol) - Find usages
- rag_stats() - Index health
- read_file(path) - Read files
- run_cmd(command) - Execute commands

Query as needed. Don't assume - ask the system.
EOF
}
```

**Benefits:**
- **~200 bytes** vs 17KB = **98.8% reduction**
- **Fresh data**: Every query hits live RAG index
- **Selective**: LLM only retrieves what it needs
- **Unified**: One MCP server, multiple clients
- **Extensible**: Add tools once, all TUIs benefit

---

## Goals & Non-Goals

### Goals

1. **Replace static context dumps** with MCP tool access in all three TUIs
2. **Maintain backward compatibility** - existing workflows still work
3. **Enable progressive adoption** - can run with or without MCP
4. **Reduce token usage** by 90%+ for typical sessions
5. **Unify tool access** across TUIs and external clients

### Non-Goals

1. **Not replacing the TUI CLIs themselves** (claude, codex, gemini stay as-is)
2. **Not changing AGENTS.md/CONTRACTS.md** (they remain as reference docs)
3. **Not building a new TUI** (reuse existing wrappers)
4. **Not requiring MCP** (graceful degradation if MCP unavailable)

---

## Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                    User (Dave)                               │
└────────────┬────────────────────────────────────────────────┘
             │
             │ Invokes wrapper
             ▼
┌─────────────────────────────────────────────────────────────┐
│  TUI Wrapper (gmaw.sh / cmw.sh / cw.sh)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ build_preamble_mcp()                                 │   │
│  │ - Minimal bootstrap prompt                           │   │
│  │ - MCP tool catalog                                   │   │
│  │ - No AGENTS.md dump                                  │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────┬────────────────────────────────────────────────┘
             │
             │ Pipes to
             ▼
┌─────────────────────────────────────────────────────────────┐
│  LLM CLI (claude / codex / gemini)                          │
│  - Receives minimal prompt                                  │
│  - Calls MCP tools as needed                                │
└────────────┬────────────────────────────────────────────────┘
             │
             │ MCP protocol (stdio)
             ▼
┌─────────────────────────────────────────────────────────────┐
│  LLMC MCP Server (llmc_mcp.server)                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Tools:                                               │   │
│  │ - rag_search, rag_where_used, rag_lineage           │   │
│  │ - inspect, rag_stats, rag_plan                      │   │
│  │ - read_file, list_dir, run_cmd                      │   │
│  │ - execute_code (code execution mode)                │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────┬────────────────────────────────────────────────┘
             │
             │ Queries
             ▼
┌─────────────────────────────────────────────────────────────┐
│  LLMC RAG System                                            │
│  - SQLite DB (.llmc/rag/index_v2.db)                        │
│  - Graph (.llmc/rag_graph.json)                             │
│  - Enrichment data                                          │
└─────────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 1. TUI Wrappers (Modified)

**Files:**
- `tools/gmaw.sh` (Gemini)
- `tools/claude_minimax_rag_wrapper.sh` (Claude/MiniMax)
- `tools/codex_rag_wrapper.sh` (Codex)

**Changes:**
- Add `build_preamble_mcp()` function (new)
- Keep `build_preamble()` for fallback (existing)
- Auto-detect MCP availability
- Switch preamble based on MCP status

#### 2. MCP Server (Existing + Enhancements)

**File:** `llmc_mcp/server.py`

**Required Tools (from section 1.8 roadmap):**
- ✅ `rag_search` (already exists)
- ✅ `read_file` (already exists)
- ✅ `list_dir` (already exists)
- ✅ `run_cmd` (already exists)
- ❌ `rag_where_used` (needs implementation)
- ❌ `rag_lineage` (needs implementation)
- ❌ `inspect` (needs implementation)
- ❌ `rag_stats` (needs implementation)
- ❌ `rag_plan` (needs implementation)

#### 3. MCP Client Library (New)

**File:** `llmc_mcp/client.py` (new)

**Purpose:** Python client for TUI wrappers to check MCP availability

```python
def is_mcp_available() -> bool:
    """Check if MCP server is running and responsive."""
    # Try to connect via stdio or unix socket
    # Return True if server responds to health check
```

---

## Detailed Design

### 1. Wrapper Modifications

#### Pattern: Dual-Mode Preamble

Each wrapper will support two modes:

1. **MCP Mode** (preferred): Minimal prompt + tool catalog
2. **Classic Mode** (fallback): Full AGENTS.md dump

```bash
# In gmaw.sh, cmw.sh, cw.sh

build_preamble() {
  if is_mcp_available; then
    build_preamble_mcp
  else
    build_preamble_classic  # Current implementation
  fi
}

is_mcp_available() {
  # Check if MCP server is running
  # Option 1: Check for running process
  pgrep -f "llmc_mcp.server" >/dev/null 2>&1 && return 0
  
  # Option 2: Try health check via Python
  python3 -c "from llmc_mcp.client import is_mcp_available; exit(0 if is_mcp_available() else 1)" 2>/dev/null && return 0
  
  return 1
}

build_preamble_mcp() {
  cat <<'EOF'
[MCP-Native Session]

You have access to LLMC tools via MCP. Use them for context retrieval.

## Core Tools

### RAG & Navigation
- **rag_search(query, limit=10)** - Semantic search across code/docs
  Returns: [{path, symbol, kind, lines, score, summary}, ...]
  
- **inspect(path=None, symbol=None, line=None)** - Deep dive into file/symbol
  Returns: {snippet, graph_relationships, enrichment, provenance}
  
- **rag_where_used(symbol, limit=10)** - Find all usages of a symbol
  Returns: [{path, line, context}, ...]
  
- **rag_lineage(symbol, direction, max_results=50)** - Dependency traversal
  direction: "upstream" (dependencies) | "downstream" (dependents)
  
- **rag_stats()** - Index health and coverage metrics

### Filesystem
- **read_file(path, max_bytes=1MB)** - Read file contents
- **list_dir(path, max_entries=1000)** - List directory
- **run_cmd(command, timeout=30)** - Execute shell command (allowlisted)

### Code Execution (Advanced)
- **execute_code(code)** - Run Python with tool stubs
  Example:
  ```python
  from stubs import rag_search, inspect
  hits = rag_search(query="authentication")
  for hit in hits['data'][:3]:
      detail = inspect(path=hit['path'])
      print(f"{hit['path']}: {detail['summary']}")
  ```

## Workflow

1. **Understand before acting**: Use rag_search or inspect to find relevant code
2. **Verify assumptions**: Use rag_where_used to check impact
3. **Navigate dependencies**: Use rag_lineage for architecture understanding
4. **Read selectively**: Only read_file after narrowing down targets

## Ground Rules

- **Query as needed** - Don't assume, ask the system
- **Prefer tools over grep** - RAG knows the structure
- **Fall back gracefully** - If tools fail, use run_cmd with rg/grep
- **Stay focused** - Retrieve only what's needed for the task

Context snapshot:
$(repo_snapshot)

EOF
}

build_preamble_classic() {
  # Existing implementation (AGENTS.md dump)
  # ... keep as-is for fallback ...
}
```

### 2. MCP Server Enhancements

#### Add Missing Tools

**Priority order** (from roadmap section 1.8):

1. **P0 - Navigation Tools**
   - `rag_where_used` - adapter exists in `tools/rag/__init__.py:143`
   - `rag_lineage` - adapter exists in `tools/rag/__init__.py:156`
   - `inspect` - needs wrapper around `tools/rag/inspector.py:217`

2. **P1 - Observability Tools**
   - `rag_stats` - direct call to `tools/rag_nav/tool_handlers.py:860`
   - `rag_plan` - wrapper around `tools/rag/planner.py:223`

**Implementation:**

```python
# In llmc_mcp/server.py

# Add to TOOLS list
Tool(
    name="rag_where_used",
    description="Find all usages of a symbol across the codebase.",
    inputSchema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Symbol name to search for"},
            "limit": {"type": "integer", "default": 10}
        },
        "required": ["symbol"]
    }
),

# Add handler
async def _handle_rag_where_used(self, args: dict) -> list[TextContent]:
    from tools.rag import tool_rag_where_used
    
    repo_root = Path(self.config.tools.allowed_roots[0])
    symbol = args.get("symbol", "")
    limit = args.get("limit", 10)
    
    result = tool_rag_where_used(
        repo_root=repo_root,
        symbol=symbol,
        limit=limit
    )
    
    return [TextContent(type="text", text=json.dumps(result, indent=2))]
```

### 3. MCP Client Library

**File:** `llmc_mcp/client.py` (new)

```python
"""Lightweight MCP client for TUI wrappers and scripts."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional


def is_mcp_available() -> bool:
    """
    Check if LLMC MCP server is running and responsive.
    
    Returns:
        True if MCP server is available, False otherwise.
    """
    try:
        # Try health check via server
        result = subprocess.run(
            [sys.executable, "-m", "llmc_mcp.server", "--health"],
            capture_output=True,
            text=True,
            timeout=2
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_mcp_tool_catalog() -> Optional[dict]:
    """
    Get list of available MCP tools.
    
    Returns:
        Dict with tool names and descriptions, or None if unavailable.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "llmc_mcp.server", "--list-tools"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return None
```

### 4. Graceful Degradation

**Fallback Strategy:**

```bash
# In wrapper main()

if is_mcp_available; then
  echo "[MCP Mode: Using tool-based context retrieval]" >&2
  PREAMBLE_MODE="mcp"
else
  echo "[Classic Mode: MCP unavailable, using static context]" >&2
  PREAMBLE_MODE="classic"
fi
```

**User Experience:**

| MCP Status | Behavior | Token Usage |
|------------|----------|-------------|
| ✅ Running | MCP mode, minimal prompt | ~200 bytes |
| ❌ Not running | Classic mode, AGENTS.md dump | ~17KB |
| ⚠️ Degraded | Classic mode + warning | ~17KB |

---

## Token Usage Analysis

### Current State (Classic Mode)

```
AGENTS.md (160 lines)        ~8,000 bytes  (~2,000 tokens)
CONTRACTS.md (160 lines)     ~6,000 bytes  (~1,500 tokens)
living_history.md (80 lines) ~3,000 bytes  (~750 tokens)
Wrapper boilerplate          ~1,000 bytes  (~250 tokens)
─────────────────────────────────────────────────────────────
Total preamble:              ~18,000 bytes (~4,500 tokens)
```

**Per-session cost:**
- Gemini 2.0 Flash: 4,500 tokens × $0.000075 = **$0.34 per session**
- Claude Sonnet 3.5: 4,500 tokens × $0.003 = **$13.50 per session**
- Codex (local): Free but wastes context window

### Proposed State (MCP Mode)

```
MCP bootstrap prompt         ~200 bytes    (~50 tokens)
Tool catalog (inline)        ~400 bytes    (~100 tokens)
Repo snapshot                ~100 bytes    (~25 tokens)
─────────────────────────────────────────────────────────────
Total preamble:              ~700 bytes    (~175 tokens)
```

**Per-session cost:**
- Gemini 2.0 Flash: 175 tokens × $0.000075 = **$0.01 per session**
- Claude Sonnet 3.5: 175 tokens × $0.003 = **$0.53 per session**

**Savings:**
- **96% token reduction** (4,500 → 175 tokens)
- **97% cost reduction** for paid APIs
- **More context window** for actual work

### Dynamic Context Retrieval

When LLM needs context, it calls tools:

```python
# Example: LLM wants to understand authentication
rag_search(query="authentication", limit=5)
# Returns ~2KB of focused results

inspect(symbol="AuthManager")
# Returns ~1KB of detailed context

# Total: ~3KB vs 18KB upfront dump
# Only retrieved when needed
```

---

## Migration Path

### Phase 1: Add MCP Support (Parallel)

**Goal:** Enable MCP mode without breaking existing workflows

1. Add `build_preamble_mcp()` to all three wrappers
2. Add `is_mcp_available()` check
3. Implement dual-mode switching
4. **No breaking changes** - classic mode still default if MCP unavailable

**Testing:**
- Run wrappers with MCP server running → MCP mode
- Run wrappers with MCP server stopped → Classic mode
- Verify both modes produce working sessions

### Phase 2: Implement Missing MCP Tools

**Goal:** Complete tool coverage for TUI use cases

1. Add `rag_where_used` to MCP server
2. Add `rag_lineage` to MCP server
3. Add `inspect` to MCP server
4. Add `rag_stats` to MCP server
5. Add `rag_plan` to MCP server

**Testing:**
- Unit tests for each new tool handler
- Integration tests via TUI wrappers
- Verify tool output matches CLI equivalents

### Phase 3: Documentation & Rollout

**Goal:** Make MCP mode discoverable and default

1. Update wrapper help text to mention MCP mode
2. Add MCP setup instructions to README
3. Update AGENTS.md to reference MCP tools
4. **Make MCP mode default** when available

**Documentation:**
```markdown
# TUI Wrappers - MCP Mode

The TUI wrappers now support MCP-native tool access for 96% token reduction.

## Setup

1. Start MCP server:
   ```bash
   llmc-mcp start
   ```

2. Run wrapper as usual:
   ```bash
   ./gmaw.sh
   ```

3. Wrapper auto-detects MCP and uses tool-based context.

## Fallback

If MCP is unavailable, wrappers fall back to classic mode (AGENTS.md dump).
```

### Phase 4: Deprecate Classic Mode (Optional)

**Goal:** Simplify maintenance by removing dual-mode complexity

1. Make MCP server auto-start on first wrapper invocation
2. Remove classic mode fallback
3. Update wrappers to require MCP

**Timeline:** 6+ months after Phase 3 rollout

---

## Implementation Details

### Wrapper-Specific Considerations

#### 1. gmaw.sh (Gemini)

**Current:** Uses `gemini -i "$(build_preamble)"` for interactive mode

**MCP Mode:**
```bash
# Interactive mode
if [ -z "$user_prompt" ]; then
  if is_mcp_available; then
    # MCP mode: minimal prompt
    gemini -i "$(build_preamble_mcp)" "${gemini_extra_args[@]}"
  else
    # Classic mode: full dump
    gemini -i "$(build_preamble_classic)" "${gemini_extra_args[@]}"
  fi
fi
```

**Gemini CLI Compatibility:**
- Gemini CLI supports MCP via `--mcp-server` flag (if available)
- Check `gemini --help` for MCP support
- May need custom MCP integration if not natively supported

#### 2. claude_minimax_rag_wrapper.sh (Claude/MiniMax)

**Current:** Uses `run_claude_with_preamble` helper

**MCP Mode:**
```bash
run_claude_with_preamble() {
  local mode="$1"
  shift
  local claude_cmd="$1"
  shift
  
  # Detect MCP availability
  local preamble_func="build_preamble_classic"
  if is_mcp_available; then
    preamble_func="build_preamble_mcp"
  fi
  
  if [ "$mode" = "interactive" ]; then
    $preamble_func | "$claude_cmd" "$@"
  else
    {
      $preamble_func
      printf '\n\n[USER REQUEST]\n%s\n' "$user_prompt"
    } | "$claude_cmd" "$@"
  fi
}
```

**Claude CLI Compatibility:**
- Claude CLI has native MCP support via `--mcp-config`
- Can specify MCP server endpoint in config
- May need to add `--mcp-config .llmc/mcp_config.json`

#### 3. codex_rag_wrapper.sh (Codex)

**Current:** Uses `build_preamble | codex ...`

**MCP Mode:**
```bash
# Interactive mode
if [ -z "$USER_PROMPT" ]; then
  if is_mcp_available; then
    build_preamble_mcp | codex ${CODEX_CONFIG_FLAG:-} -C "$REPO_ROOT" ${CODEX_FLAGS:-}
  else
    build_preamble_classic | codex ${CODEX_CONFIG_FLAG:-} -C "$REPO_ROOT" ${CODEX_FLAGS:-}
  fi
  exit $?
fi
```

**Codex CLI Compatibility:**
- Check if Codex supports MCP natively
- May need to use `--tools` flag to expose MCP tools
- Fallback: Use classic mode if MCP not supported

### MCP Server Lifecycle

**Auto-Start Pattern:**

```bash
# In wrapper main()

ensure_mcp_server() {
  if ! is_mcp_available; then
    echo "[Starting MCP server...]" >&2
    python3 -m llmc_mcp.server --daemon &
    sleep 1  # Wait for startup
    
    if ! is_mcp_available; then
      echo "[Warning: MCP server failed to start, using classic mode]" >&2
      return 1
    fi
  fi
  return 0
}

# Call before building preamble
ensure_mcp_server || true
```

**Daemon Management:**

```bash
# Start MCP server in background
llmc-mcp start

# Stop MCP server
llmc-mcp stop

# Check status
llmc-mcp status
```

---

## Testing Strategy

### Unit Tests

**File:** `tests/test_tui_mcp_integration.py`

```python
def test_is_mcp_available_when_running():
    """Test MCP availability check when server is running."""
    # Start MCP server
    # Check is_mcp_available() returns True
    
def test_is_mcp_available_when_stopped():
    """Test MCP availability check when server is stopped."""
    # Ensure MCP server is not running
    # Check is_mcp_available() returns False

def test_preamble_mcp_mode():
    """Test MCP mode preamble is minimal."""
    preamble = build_preamble_mcp()
    assert len(preamble) < 1000  # Much smaller than classic
    assert "rag_search" in preamble
    assert "inspect" in preamble

def test_preamble_classic_mode():
    """Test classic mode preamble includes AGENTS.md."""
    preamble = build_preamble_classic()
    assert len(preamble) > 10000  # Full dump
    assert "AGENTS.md" in preamble or "Context Retrieval" in preamble
```

### Integration Tests

**File:** `tests/test_tui_wrappers_e2e.py`

```python
def test_gmaw_mcp_mode():
    """Test gmaw.sh in MCP mode."""
    # Start MCP server
    # Run: ./gmaw.sh "What is the RAG search function?"
    # Verify: Output includes rag_search results
    # Verify: No AGENTS.md dump in logs

def test_gmaw_classic_fallback():
    """Test gmaw.sh falls back to classic mode."""
    # Stop MCP server
    # Run: ./gmaw.sh "What is the RAG search function?"
    # Verify: Output includes AGENTS.md context
    # Verify: Warning about MCP unavailable

def test_cmw_mcp_mode():
    """Test claude_minimax_rag_wrapper.sh in MCP mode."""
    # Similar to gmaw test

def test_cw_mcp_mode():
    """Test codex_rag_wrapper.sh in MCP mode."""
    # Similar to gmaw test
```

### Manual Testing

**Checklist:**

- [ ] Start MCP server, run each wrapper in interactive mode
- [ ] Verify minimal preamble (check logs/stderr)
- [ ] Ask LLM to use rag_search, inspect, rag_where_used
- [ ] Verify tool calls succeed and return expected data
- [ ] Stop MCP server, run each wrapper again
- [ ] Verify fallback to classic mode with AGENTS.md dump
- [ ] Measure token usage (compare MCP vs classic)

---

## Risks & Mitigations

### Risk 1: MCP Server Unavailability

**Problem:** If MCP server crashes mid-session, LLM loses tool access.

**Mitigation:**
- Graceful degradation: Fall back to classic mode on tool errors
- Auto-restart: Wrapper detects MCP failure and restarts server
- Clear error messages: "MCP tools unavailable, using classic mode"

### Risk 2: LLM Doesn't Use Tools

**Problem:** LLM ignores MCP tools and tries to answer from memory.

**Mitigation:**
- Strong prompt engineering: "You MUST use tools for context"
- Examples in preamble: Show tool usage patterns
- Verification: Test with known queries that require tools

### Risk 3: Tool Call Overhead

**Problem:** Multiple tool calls add latency vs. upfront context dump.

**Mitigation:**
- Optimize tool response times (< 150ms p95)
- Batch tool calls when possible (execute_code mode)
- Cache frequently accessed data (rag_stats, repo snapshot)

### Risk 4: Breaking Existing Workflows

**Problem:** Users rely on current wrapper behavior.

**Mitigation:**
- Dual-mode support: Classic mode always available
- Gradual rollout: MCP mode opt-in initially
- Clear migration path: Document changes and benefits

---

## Success Metrics

### Quantitative

| Metric | Baseline (Classic) | Target (MCP) | Measurement |
|--------|-------------------|--------------|-------------|
| Preamble token count | 4,500 tokens | < 200 tokens | Token counter |
| Session cost (Gemini) | $0.34 | < $0.02 | API billing |
| Session cost (Claude) | $13.50 | < $0.60 | API billing |
| Time to first response | ~3s | < 2s | Stopwatch |
| Tool call latency | N/A | < 150ms p95 | MCP telemetry |

### Qualitative

- [ ] LLMs successfully use RAG tools without prompting
- [ ] Users report faster, more focused responses
- [ ] No increase in "I don't know" responses
- [ ] Easier to debug (tool calls visible in logs)

---

## Open Questions

1. **CLI MCP Support:**
   - Does Gemini CLI support MCP natively?
   - Does Codex CLI support MCP natively?
   - Do we need custom integration for each?

2. **Session State:**
   - Should MCP server maintain session state across wrapper invocations?
   - How to handle multi-turn conversations with tool context?

3. **Tool Discovery:**
   - Should preamble list all tools or just categories?
   - How to handle tool additions without updating wrappers?

4. **Caching:**
   - Should frequently accessed data (repo snapshot, rag_stats) be cached?
   - What's the cache invalidation strategy?

5. **Error Handling:**
   - What happens if a tool call fails mid-session?
   - Should wrapper retry or fall back to classic mode?

---

## Future Enhancements

### Phase 5: Advanced Features (P2)

1. **Session Persistence:**
   - Save tool call history across sessions
   - Resume previous context without re-querying

2. **Smart Caching:**
   - Cache rag_search results for common queries
   - Invalidate on file changes (via inotify)

3. **Tool Composition:**
   - LLM chains multiple tools automatically
   - Example: rag_search → inspect → rag_where_used

4. **Cost Tracking:**
   - Log token usage per session
   - Compare MCP vs classic mode savings

5. **Multi-Repo Support:**
   - MCP server handles multiple repos
   - Wrappers specify target repo in tool calls

---

## References

- [MCP Tool Gaps Analysis](file:///home/vmlinux/.gemini/antigravity/brain/50bbb1b1-feba-4d32-b2ad-d6b7258fefaa/mcp_tool_gaps.md)
- [MCP Telemetry Design](file:///home/vmlinux/.gemini/antigravity/brain/50bbb1b1-feba-4d32-b2ad-d6b7258fefaa/mcp_telemetry_design.md)
- [ROADMAP.md](file:///home/vmlinux/src/llmc/DOCS/ROADMAP.md) - Section 1.8 (MCP Tool Expansion)
- [AGENTS.md](file:///home/vmlinux/src/llmc/AGENTS.md) - Current context protocol
- [gmaw.sh](file:///home/vmlinux/src/llmc/tools/gmaw.sh) - Gemini wrapper
- [claude_minimax_rag_wrapper.sh](file:///home/vmlinux/src/llmc/tools/claude_minimax_rag_wrapper.sh) - Claude wrapper
- [codex_rag_wrapper.sh](file:///home/vmlinux/src/llmc/tools/codex_rag_wrapper.sh) - Codex wrapper
