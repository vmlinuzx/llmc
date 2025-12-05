# RMTA Quick Reference

## One-Liner Usage

### MiniMax Version (Default)
```bash
# Default: Test all MCP tools and generate report
./tools/ruthless_mcp_tester.sh

# Custom focus area
./tools/ruthless_mcp_tester.sh "Focus on RAG navigation tools"

# Interactive TUI mode
./tools/ruthless_mcp_tester.sh --tui
```

### Gemini Version
```bash
# Default: Test all MCP tools with Gemini
./tools/ruthless_mcp_tester_gemini.sh

# Custom focus area
./tools/ruthless_mcp_tester_gemini.sh "Focus on RAG navigation tools"

# Specify repo
./tools/ruthless_mcp_tester_gemini.sh --repo /path/to/llmc
```

## Environment Setup

### MiniMax/Claude Version
```bash
# Required
export ANTHROPIC_AUTH_TOKEN="sk-..."

# Optional (defaults shown)
export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
export ANTHROPIC_MODEL="MiniMax-M2"
export API_TIMEOUT_MS="3000000"
export CLAUDE_CMD="claude"
```

### Gemini Version
```bash
# No API key needed - uses logged-in Google account via gemini TUI

# Optional (default shown)
export GEMINI_MODEL="gemini-3-pro-preview"
```

## Report Location

Reports are saved to:
```
tests/REPORTS/mcp/rmta_report_YYYYMMDD_HHMMSS.md
```

## Severity Levels

| Level | Meaning | Example |
|-------|---------|---------|
| **P0** | Critical - Core broken | `rag_search` returns errors |
| **P1** | High - Advertised tool broken | `rag_where_used` missing handler |
| **P2** | Medium - Works but buggy | `linux_fs_edit` wrong metadata |
| **P3** | Low - UX papercut | Confusing error message |

## Expected Findings (from 2025-12-04 AAR)

### P1 - Missing Handlers
- `rag_where_used`
- `rag_lineage`
- `rag_stats`
- `inspect`

### P1 - Stub Implementations
- `linux_proc_list` (returns empty)
- `linux_sys_snapshot` (N/A values)
- `linux_proc_*` REPLs (all empty)

### P2 - Response Bugs
- `linux_fs_edit` (incorrect `replacements_made`)
- `rag_query` (`summary: None`)
- `stat` (minimal metadata)

## What RMTA Tests

✅ **Bootstrap** - `00_INIT` tool accuracy  
✅ **Discovery** - Tool listing completeness  
✅ **Functionality** - Each tool with realistic inputs  
✅ **UX** - Error messages, defaults, documentation  
✅ **Alignment** - Advertised vs implemented features

## What RMTA Does NOT Test

❌ **Security** - Use `ren_ruthless_security_agent.sh`  
❌ **Performance** - Use benchmarking tools  
❌ **Internal APIs** - Use unit tests  
❌ **Adversarial inputs** - Use fuzzing tools

## Success Criteria

A good RMTA run:
- Tests 80%+ of advertised tools
- Finds P0/P1 bugs if they exist
- Zero false positives
- Actionable incidents with repro steps
- Prioritized recommendations

**Finding bugs = SUCCESS!**

## Roadmap Integration

**1.0** - RMTA implementation (Phase 1 ✅ Complete)  
**1.0.1** - Fix bugs found by RMTA (Blocked, awaiting first run)

See: `DOCS/ROADMAP.md` and `DOCS/planning/HLD_Ruthless_MCP_Testing_Agent.md`
