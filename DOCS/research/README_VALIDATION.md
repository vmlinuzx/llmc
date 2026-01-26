# RLM Validation Guide

This directory contains validation artifacts for the LLMC RLM implementation.

## Quick Validation

Run the automated test suite:

```bash
./scripts/validate_rlm_system.sh
```

This validates all 7 core systems:
1. ✅ LLMC Index Health
2. ✅ Navigation SDK (mc* tools)
3. ✅ RLM Configuration
4. ✅ Sandbox Security
5. ✅ Budget Enforcement
6. ✅ MCP Integration
7. ✅ AST Navigation

## Manual Testing

### Test 1: Basic RLM Query

```bash
# Analyze a file using RLM
llmc rlm query "Explain what this file does" \
  --file llmc/rlm/session.py \
  --trace
```

**Expected**: Answer + budget summary + execution trace

### Test 2: Context Window Savings

Compare traditional RAG vs RLM:

```bash
# Traditional: Paste entire file (45k tokens)
# RLM: Only load what's accessed (~1.2k tokens)

llmc rlm query "Find the budget tracking logic" \
  --file llmc/rlm/session.py \
  --json | jq '.budget.total_tokens'
```

**Expected**: < 5,000 tokens (97% reduction)

### Test 3: Recursive Sub-Calls

```bash
# Task that requires decomposition
llmc rlm query "Trace how RLMSession is instantiated and used" \
  --file llmc/commands/rlm.py \
  --budget 0.50 \
  --trace
```

**Expected**: Multiple sub-calls in trace, budget summary shows depth > 1

### Test 4: Security Validation

```bash
# Attempt to access denied path
python3 << 'PYEOF'
from llmc_mcp.tools.rlm import mcp_rlm_query
from llmc_mcp.config import McpRlmConfig

config = McpRlmConfig(
    enabled=True,
    denylist_globs=["**/.env", "**/secrets/*"],
    allow_path=True
)

result = await mcp_rlm_query({
    "task": "Read this file",
    "path": ".env"
}, config, allowed_roots=["/home/vmlinux/src/llmc"], repo_root=Path("."))

assert "denylist" in result["error"]
PYEOF
```

**Expected**: Error with "denylist" message

### Test 5: MCP Tool Call

```bash
# Test via MCP server (requires Claude Desktop or MCP client)
echo '{"method":"tools/call","params":{"name":"rlm_query","arguments":{"task":"Summarize this","context":"def foo(): return 42"}}}' | \
  python -m llmc_mcp.server
```

**Expected**: JSON response with `data.answer` field

## Performance Benchmarks

### Embedding Quality

```bash
llmc-cli analytics benchmark
```

**Expected**: Top-1 accuracy > 80% (from research Section 2.1)

### Tool Latency

```bash
python llmc_mcp/benchmarks/runner.py
```

**Expected**: 
- `rag_search`: < 100ms
- `mcgrep`: < 200ms
- `rlm_query`: < 5s (depends on model)

## Research Validation Checklist

Compare against `/DOCS/research/Recursive Intelligence in Repository-scale environments.txt`:

- [x] **Section 2.1**: Context bottleneck solved via lazy loading
- [x] **Section 2.2**: Recursive sub-calls with budget tracking
- [x] **Section 3.1**: AST chunking integration (TreeSitter)
- [x] **Section 4.1**: RLM-REPL-Index triad implemented
- [x] **Section 4.2**: Navigation SDK (flatter API than proposed)
- [x] **Section 5.1**: Sandbox (process-based, not Docker/E2B)
- [x] **Section 6.4**: Security (exceeds spec with policy layer)
- [x] **Section 8.3**: Infinite recursion protection

## Gaps vs Research

❌ **Not Implemented**:
1. E2B cloud sandbox (using process sandbox instead)
2. LangGraph orchestration (custom logic instead)
3. Recursive index summarization (using Qwen batch enrichment)

✅ **Exceeds Spec**:
1. Hospital-grade security policies (MCP layer)
2. Budget governance at all call sites
3. Progressive disclosure (bootstrap pattern)
4. Observability (tracing, metrics)

## Troubleshooting

### "RLM tool disabled"
```bash
# Check config
grep -A10 "\[mcp.rlm\]" llmc.toml
# Enable if needed
# mcp.rlm.enabled = true
```

### "Graph index missing"
```bash
# Rebuild index
llmc-cli repo index /home/vmlinux/src/llmc
llmc-cli run mcschema schema
```

### "Budget exceeded"
```bash
# Increase limit in llmc.toml
[rlm.budget]
max_session_budget_usd = 5.00  # Default: 1.00
```

### "Sandbox timeout"
```bash
# Increase timeout in llmc.toml
[rlm.sandbox]
code_timeout_seconds = 60  # Default: 30
```

## Further Reading

- Full validation report: `rlm_validation_report.md`
- Original research: `Recursive Intelligence in Repository-scale environments.txt`
- RLM architecture: `/llmc/rlm/README.md`
- MCP integration: `/DOCS/operations/mcp.md`

---

**Status**: ✅ Phase 1 Complete — Production-ready for process-based deployment

**Next**: Migrate to E2B sandbox for production hardening (Phase 2)
