# RMTA - Ruthless MCP Testing Agent Reports

This directory contains test reports from the **Ruthless MCP Testing Agent (RMTA)**, an automated agent-based testing harness for the LLMC MCP server.

## What is RMTA?

RMTA is an LLM-in-the-loop testing system that validates the MCP server by:
1. **Acting as a real agent** - Uses only the MCP interface (no internal APIs)
2. **Exercising all advertised tools** - Discovers and tests every tool systematically
3. **Analyzing its own experience** - Reports UX issues, broken tools, documentation drift
4. **Running continuously** - Can be invoked in CI or on-demand

**Key Insight:** Traditional unit tests verify code *can* be called. RMTA verifies that the **agent experience matches what we promise**.

## Running RMTA

### Autonomous Mode (Default)
```bash
# From repo root
./tools/ruthless_mcp_tester.sh

# With custom focus
./tools/ruthless_mcp_tester.sh "Focus on RAG tools only"

# From tools directory
cd tools
./ruthless_mcp_tester.sh
```

### Interactive TUI Mode
```bash
./tools/ruthless_mcp_tester.sh --tui
```

### Environment Setup
```bash
# Required: MiniMax API key (or other Anthropic-compatible endpoint)
export ANTHROPIC_AUTH_TOKEN="sk-..."

# Optional: Override defaults
export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
export ANTHROPIC_MODEL="MiniMax-M2"
export CLAUDE_CMD="claude"  # or "claude-code"
```

## Report Format

Each report follows this structure:

```markdown
# RMTA Report - <TIMESTAMP>

## Summary
- Total tools tested
- Working / Buggy / Broken / Not tested counts

## Bootstrap Validation
- Bootstrap tool availability and accuracy

## Tool Inventory
- Complete list of discovered tools

## Test Results
- Working Tools (✅)
- Buggy Tools (⚠️)
- Broken Tools (❌)
- Not Tested (🚫)

## Incidents (Prioritized)
- P0 (Critical): Core features broken
- P1 (High): Advertised tools missing/broken
- P2 (Medium): Buggy working features  
- P3 (Low): UX papercuts

## Documentation Drift
- Tools advertised but not implemented
- Misleading descriptions
- Incorrect examples

## Recommendations
- Prioritized action items
```

## Severity Guidelines

**P0 - Critical:**
- Core features completely broken (`rag_search` returns errors)
- Bootstrap tool missing or incorrect
- MCP server crashes

**P1 - High:**
- Advertised tool missing handler
- Wrong data structure returned
- Documented workflow doesn't work

**P2 - Medium:**
- Metadata bugs (wrong counts, null fields)
- Confusing error messages
- Missing defaults

**P3 - Low:**
- Minor UX issues
- Documentation typos
- Suboptimal naming

## Integration with Roadmap

RMTA findings feed directly into roadmap items:
- **1.0** - RMTA implementation (this agent)
- **1.0.1** - MCP Tool Alignment (fixing bugs found by RMTA)

See `DOCS/ROADMAP.md` section 1.0 and `DOCS/planning/HLD_Ruthless_MCP_Testing_Agent.md` for full design.

## Success Criteria

A good RMTA run:
- ✅ Tests at least 80% of advertised tools
- ✅ Finds P0/P1 issues if they exist (no false negatives)
- ✅ Zero false positives (no incorrect failures)
- ✅ Actionable incidents with repro steps
- ✅ Prioritized recommendations

**Remember:** Finding bugs is success! A perfect report means you didn't test hard enough.

## Historical Context

**2025-12-04 AAR:** Manual MCP testing revealed:
- 35% of advertised tools non-functional
- Bootstrap instructions with incorrect paths
- Missing handlers for `rag_where_used`, `rag_lineage`, `rag_stats`, `inspect`
- Response format bugs in `linux_fs_edit`
- Stub implementations returning empty data

RMTA was created to automate this validation and prevent regressions.

## Next Steps

**Phase 1 (Current):** Shell wrapper + prompts (manual invocation)  
**Phase 2:** Python orchestrator (`llmc test-mcp --mode ruthless`)  
**Phase 3:** CI integration with quality gates  
**Phase 4:** Historical tracking and regression detection
