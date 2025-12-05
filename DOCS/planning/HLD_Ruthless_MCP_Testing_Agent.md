# High-Level Design - Ruthless MCP Testing Agent (RMTA)
**Version:** v1.0  
**Date:** 2025-12-04  
**Owner:** LLMC  
**Status:** Draft - Ready for Implementation  
**Priority:** P0 (Critical Infrastructure)

---

## 0. Executive Summary

The **Ruthless MCP Testing Agent (RMTA)** is an **LLM-in-the-loop testing harness** that systematically validates the LLMC MCP server by:

1. **Acting as a real agent** - Uses only the MCP interface (no internal APIs)
2. **Exercising all advertised tools** - Discovers and tests every stub/tool
3. **Analyzing its own experience** - Reports UX issues, broken tools, documentation drift
4. **Running continuously** - Can be invoked in CI or on-demand

**Key Insight:** Traditional unit tests verify that code *can* be called. RMTA verifies that the **agent experience matches what we promise**.

**Why P0:**
- MCP is the primary interface for Claude Desktop and other agent integrations
- A broken MCP server = broken user experience for *all* agent users
- Recent AAR (2025-12-04) found 35% of advertised tools non-functional
- No existing test catches "documentation drift" (prompts that lie about paths/capabilities)

---

## 1. Goals and Non-Goals

### 1.1 Goals

1. **Systematic Tool Coverage**
   - Discover all tools via `list_tools` MCP protocol
   - Execute each tool with realistic inputs
   - Report which tools work, which are stubs, which error

2. **Agent UX Validation**
   - Verify `00_INIT` bootstrap instructions are accurate
   - Test tool discovery flow (can agent find stubs?)
   - Detect confusing error messages, incorrect defaults, path issues

3. **Documentation Alignment**
   - Compare advertised capabilities (`BOOTSTRAP_PROMPT`, tool descriptions) with actual behavior
   - Flag tools listed in docs but missing handlers
   - Flag tools with misleading descriptions

4. **Continuous Validation**
   - Can run in CI (deterministic mode)
   - Can run on-demand for exploratory testing
   - Outputs structured reports (pass/fail per tool, incidents)

5. **Self-Analysis and Reporting**
   - Agent reflects on its own testing experience
   - Reports: "I tried to use X but the prompt said Y and it failed because Z"
   - Prioritizes findings by severity (P0 = broken core feature, P3 = minor UX papercut)

### 1.2 Non-Goals (for v1)

- **No implementation fixes** - RMTA reports bugs, doesn't patch them
- **No fuzzing or adversarial testing** - RMTA uses realistic inputs, not random garbage (that's for Phase 2)
- **No performance benchmarking** - Focus on correctness and UX, not latency (can add in Phase 3)
- **No GUI dashboard** - Outputs markdown and JSON for humans/CI to consume

---

## 2. Architecture

### 2.1 Components

```
┌─────────────────────────────────────────────────────────────┐
│                    RMTA Orchestrator                         │
│  (CLI: llmc test-mcp --mode ruthless)                       │
└──────────────┬──────────────────────────────────────────────┘
               │
               ├─► 1. Bootstrap Validator
               │      - Reads 00_INIT output
               │      - Verifies path accuracy, tool list completeness
               │
               ├─► 2. Tool Discovery Agent (LLM)
               │      - Lists all tools via MCP
               │      - Reads stub signatures (if code_exec mode)
               │      - Builds test plan
               │
               ├─► 3. Tool Executor Agent (LLM)
               │      - For each tool: invoke with realistic args
               │      - Logs: request, response, success/fail
               │      - Uses only MCP interface (no cheating)
               │
               ├─► 4. Experience Analyzer (LLM)
               │      - Reviews execution logs
               │      - Identifies: broken tools, confusing UX, doc drift
               │      - Generates incidents with severity
               │
               └─► 5. Report Generator
                      - Outputs:
                        • Markdown test report (human-readable)
                        • JSON summary (CI-parseable)
                        • Incident list (for roadmap integration)
```

### 2.2 Data Flow

1. **Invocation**
   ```bash
   llmc test-mcp --mode ruthless --report artifacts/rmta/report.md
   ```

2. **Bootstrap Validation**
   - RMTA connects to MCP server
   - Calls `00_INIT` tool
   - Parses instructions
   - Validates: Are stub paths correct? Are all listed tools present?

3. **Tool Discovery**
   - LLM agent queries MCP for tool list
   - In code_exec mode: lists `.llmc/stubs/` directory
   - Builds inventory: {tool_name, description, required_args, optional_args}

4. **Execution Phase**
   - For each tool, LLM agent:
     - Decides realistic test case (e.g., `read_file` → read a small config file)
     - Invokes tool via MCP
     - Logs result
   - Handles errors gracefully (doesn't crash on first failure)

5. **Analysis Phase**
   - LLM reviews execution log
   - Classifies each tool: ✅ Works, ⚠️ Works but buggy, ❌ Not implemented
   - Identifies UX issues: confusing prompts, incorrect docs, missing features

6. **Report Generation**
   - Generates markdown report with:
     - Summary table (tool status)
     - Detailed findings (per tool)
     - Incidents (severity, repro steps, evidence)
   - Generates JSON summary for CI

---

## 3. Agent Prompts

### 3.1 Tool Discovery Agent Prompt

```markdown
Role: You are RMTA-Discovery, a tool inventory agent for LLMC MCP server testing.

Your goal: Systematically discover all available MCP tools and build a test plan.

Process:
1. Call the `00_INIT` tool to get bootstrap instructions
2. Parse the instructions to find:
   - Location of stubs (if code_exec mode)
   - List of advertised tools
3. Call `list_tools` (MCP protocol) to get actual registered tools
4. If code_exec mode: use `list_dir` on stubs directory to find all stubs
5. Build an inventory: {tool_name, source (registered vs stub), description}
6. Output a JSON list of tools to test

Output Format:
{
  "tools_to_test": [
    {
      "name": "rag_query",
      "source": "registered",
      "description": "Query the RAG system...",
      "required_args": ["query"],
      "optional_args": ["k", "index"]
    },
    ...
  ],
  "discrepancies": [
    "Tool 'rag_where_used' listed in BOOTSTRAP_PROMPT but not registered"
  ]
}
```

### 3.2 Tool Executor Agent Prompt

```markdown
Role: You are RMTA-Executor, a tool testing agent.

Your goal: Execute each tool from the test plan with realistic inputs.

Constraints:
- Use ONLY the MCP interface (tools exposed by the server)
- Do NOT access internal APIs, file system directly, or test frameworks
- For each tool:
  1. Decide a realistic test case (e.g., search for "routing", read a config file)
  2. Invoke the tool
  3. Log the result: success/fail, response summary, any errors
  4. If it fails, note whether it's:
     - Missing handler ("Unknown tool")
     - Bad arguments (validation error)
     - Runtime error (exception/traceback)
     - Silent failure (no error but wrong result)

Process:
For each tool in the test plan:
- Step 1: Describe what you're testing and why
- Step 2: Invoke the tool
- Step 3: Log the result
- Step 4: Move to next tool (do NOT retry failures unless instructed)

Output Format (JSONL):
{"tool": "rag_query", "status": "success", "response": {...}, "notes": "Returned 5 results"}
{"tool": "rag_where_used", "status": "error", "error": "Unknown tool", "notes": "Handler missing"}
...
```

### 3.3 Experience Analyzer Prompt

```markdown
Role: You are RMTA-Analyzer, a UX and quality evaluator for MCP server testing.

Your inputs:
- Bootstrap instructions (from 00_INIT)
- Tool inventory (from Discovery phase)
- Execution log (from Executor phase)

Your goal:
Analyze the testing session from an agent's perspective and identify:
1. **Broken Tools** - Advertised but don't work
2. **Documentation Drift** - Prompts/docs that lie or mislead
3. **UX Issues** - Confusing errors, poor defaults, unexpected behavior
4. **Data Quality** - Missing fields, inconsistent formats

For each issue:
- Classify severity:
  - P0: Core feature broken (e.g., rag_query returns errors)
  - P1: Advertised tool non-functional (e.g., rag_where_used missing handler)
  - P2: Tool works but has bugs (e.g., incorrect metadata in response)
  - P3: Minor UX issue (e.g., error message could be clearer)
- Provide:
  - Title
  - Repro steps (what you did)
  - Expected vs actual behavior
  - Evidence (tool response, error message)

Output Format (JSON):
{
  "summary": {
    "total_tools_tested": 25,
    "working": 15,
    "broken": 5,
    "buggy": 3,
    "not_tested": 2
  },
  "incidents": [
    {
      "id": "RMTA-001",
      "severity": "P1",
      "tool": "rag_where_used",
      "title": "Graph tool advertised but not implemented",
      "repro": ["Call rag_where_used(symbol='EnrichmentPipeline')"],
      "expected": "List of files using the symbol",
      "actual": "Error: Unknown tool",
      "evidence": "{\"error\": \"Unknown tool: rag_where_used\"}"
    },
    ...
  ]
}
```

---

## 4. Implementation Plan

### Phase 1: Minimal Harness (P0, 1-2 days)
**Deliverables:**
- Script: `tools/ruthless_mcp_tester.sh` (wrapper around Gemini/Claude TUI)
- Agent prompts (Tool Discovery, Executor, Analyzer)
- Manual invocation: run agent, generates report in `tests/REPORTS/mcp/`

**Success Criteria:**
- Agent can connect to MCP server
- Agent can list tools and invoke 5-10 of them
- Agent generates a markdown report

### Phase 2: Automated Orchestrator (P0, 2-3 days)
**Deliverables:**
- Python orchestrator: `llmc_mcp/test_harness.py`
- CLI integration: `llmc test-mcp --mode ruthless`
- JSON output for CI parsing

**Success Criteria:**
- Can run unattended (no manual agent invocation)
- Deterministic mode (fixed model, low temperature)
- Exit code reflects test outcome (0 = pass, 1 = failures found)

### Phase 3: CI Integration (P1, 1 day)
**Deliverables:**
- CI workflow: `.github/workflows/mcp-ruthless-test.yml`
- Quality gate: fail CI if P0 incidents detected
- Scheduled runs (daily or on MCP server changes)

**Success Criteria:**
- PR checks include MCP ruthless test
- Reports archived as CI artifacts
- Slack/Discord notification on failures (optional)

### Phase 4: Enhanced Analysis (P2, 2-3 days)
**Deliverables:**
- Comparative analysis: "Did this PR make things better or worse?"
- Historical tracking: store test results in SQLite
- Regression detection: "rag_query worked yesterday, broken today"

**Success Criteria:**
- Agent can say "This commit broke 3 tools that worked before"
- Trend graphs (optional, if time permits)

---

## 5. Test Scenarios

### 5.1 Happy Path Tests
For each tool category:

**RAG Tools:**
- `rag_query("routing")` → expect results
- `rag_query("nonexistent_gibberish_12345")` → expect 0 results (not error)

**File System:**
- `read_file("pytest.ini")` → expect content
- `list_dir("/home/vmlinux/src/llmc")` → expect entries
- `linux_fs_write("/tmp/test.txt", "hello")` → expect success

**Commands:**
- `run_cmd("echo hello")` → expect stdout="hello"
- `run_cmd("invalid_command_xyz")` → expect error (not crash)

### 5.2 Negative Tests
- Call tool with missing required arg → expect validation error
- Call non-existent tool → expect "Unknown tool" error (not exception)
- Call tool with wrong type → expect type error (not silent failure)

### 5.3 UX Tests
- Follow `00_INIT` instructions verbatim → should succeed
- Try to list stubs using path from docs → should work (not "outside allowed roots")

### 5.4 Documentation Alignment
- For each tool in `BOOTSTRAP_PROMPT`:
  - Verify it has a handler
  - Verify description matches behavior
- For each tool in `TOOLS` array:
  - Verify it's listed in docs (or marked experimental)

---

## 6. Output Formats

### 6.1 Markdown Report

```markdown
# RMTA Report - 2025-12-04T11:30:00Z

## Summary
- **Total Tools Tested:** 25
- **✅ Working:** 15
- **⚠️ Buggy:** 3
- **❌ Broken:** 5
- **⏭️ Skipped:** 2

## Incidents

### RMTA-001: [P1] Graph tools advertised but not implemented
**Tool:** `rag_where_used`
**Severity:** P1
**Status:** ❌ BROKEN

**What I Tried:**
Called `rag_where_used(symbol="EnrichmentPipeline", limit=10)`

**Expected:**
List of files where the symbol is used

**Actual:**
`{"error": "Unknown tool: rag_where_used"}`

**Evidence:**
Tool is listed in BOOTSTRAP_PROMPT but handler missing from server.py

**Recommendation:**
Either implement handler or remove from advertised tools.

---

### RMTA-002: [P2] linux_fs_edit returns incorrect replacement count
...

## Tool Status Table

| Tool | Status | Notes |
|------|--------|-------|
| rag_query | ✅ Works | Some results missing `summary` field |
| rag_where_used | ❌ Broken | Handler not registered |
| read_file | ✅ Works | Clean |
| linux_fs_edit | ⚠️ Buggy | Reports 0 replacements but edit applied |
| ... | ... | ... |

## Agent Experience Notes

During testing, I encountered the following UX issues:
1. Bootstrap instructions said to use `list_dir('.llmc/stubs/')` but path was incorrect (had to use full path)
2. Error messages were clear for most failures
3. Response formats are inconsistent (some tools return `data`, others return `result`)

## Recommendations

**P0 - Critical:**
1. Fix bootstrap path in EXECUTE_CODE_TOOL description
2. Remove non-implemented tools from BOOTSTRAP_PROMPT

**P1 - High:**
3. Implement handlers for graph tools (rag_where_used, etc.)
4. Standardize response format across all tools

**P2 - Medium:**
5. Fix linux_fs_edit metadata bug
6. Guarantee non-null summaries in RAG results
```

### 6.2 JSON Summary (for CI)

```json
{
  "run_id": "rmta_2025-12-04T11:30:00Z",
  "timestamp": "2025-12-04T11:30:00Z",
  "mcp_server_version": "v1.2.3",
  "summary": {
    "total_tools": 25,
    "working": 15,
    "broken": 5,
    "buggy": 3,
    "skipped": 2
  },
  "incidents": [
    {
      "id": "RMTA-001",
      "severity": "P1",
      "tool": "rag_where_used",
      "title": "Graph tool advertised but not implemented",
      "status": "broken"
    }
  ],
  "verdict": "FAIL",
  "p0_count": 0,
  "p1_count": 5,
  "exit_code": 1
}
```

---

## 7. Deployment Strategy

### 7.1 Initial Rollout
1. Deploy to `tools/ruthless_mcp_tester.sh` for manual testing
2. Run ad-hoc after MCP server changes
3. Iterate on prompts based on early results

### 7.2 CI Integration
1. Add to PR checks (non-blocking initially)
2. Monitor false positive rate for 1 week
3. Make blocking if <5% false positives

### 7.3 Continuous Operation
1. Daily scheduled runs (nightly CI)
2. Archive reports in `artifacts/rmta/`
3. Trend analysis (weekly review of historical data)

---

## 8. Risks and Mitigations

### 8.1 Flaky Results (LLM non-determinism)
**Risk:** Agent might report different findings on same codebase

**Mitigation:**
- Use deterministic config (low temperature, fixed model)
- For critical tests, run 3 times and take majority vote
- Focus on objective checks (tool exists? returns error?) over subjective UX

### 8.2 Test Cost
**Risk:** Running LLM on 25+ tools = expensive/slow

**Mitigation:**
- Tiered test suites: "smoke" (5 tools, fast), "full" (all tools, nightly)
- Cache tool discovery results (only re-run if server.py changes)
- Use cheaper models for known-working tools (Haiku), expensive models for analysis

### 8.3 Coverage Gaps
**Risk:** Agent might not test all edge cases

**Mitigation:**
- RMTA tests "happy path + documented behavior"
- Traditional unit tests cover edge cases and error handling
- Security agent covers adversarial inputs
- All three together = comprehensive coverage

---

## 9. Success Metrics

### Short-Term (Week 1)
- [ ] RMTA can run unattended and generate report
- [ ] RMTA finds the 5 known broken tools from 2025-12-04 AAR
- [ ] Zero false positives (tools marked broken that actually work)

### Medium-Term (Month 1)
- [ ] CI integration complete (runs on every MCP server change)
- [ ] 100% of tools in `BOOTSTRAP_PROMPT` tested
- [ ] Incidents feed into roadmap (auto-create issues?)

### Long-Term (Quarter 1)
- [ ] Zero P0/P1 incidents in production
- [ ] Historical trend shows decreasing incident count
- [ ] Agent UX score improves (subjective, but tracked)

---

## 10. Inspiration and Prior Art

**Existing LLMC Agents:**
- `tools/ren_ruthless_testing_agent.sh` - Tests codebase features via Git+CLI
- `tools/ren_ruthless_security_agent.sh` - Tests sandbox security
- `DOCS/planning/SDD_RUTA_Ruthless_User_Testing_Agent.md` - End-to-end user flows

**Key Differences for RMTA:**
- **Scope:** MCP server interface only (not full codebase)
- **Method:** Agent uses MCP exclusively (no git, no direct file access)
- **Focus:** Tool availability, UX, documentation alignment

**External Inspiration:**
- Anthropic's "Model Context Protocol" testing practices
- LangChain's tool testing harness
- Metamorphic testing for search systems (RUTA SDD section 4.3)

---

## 11. Conclusion

The Ruthless MCP Testing Agent fills a critical gap in LLMC's testing strategy:

**Traditional Tests:** Verify code correctness  
**RMTA:** Verifies **agent experience** matches **promises**

By running RMTA continuously, we ensure:
1. MCP server always works as documented
2. Agents (human or AI) trust the tool ecosystem
3. Regressions are caught before they reach users

**Next Steps:**
1. Implement Phase 1 (minimal harness)
2. Run against current MCP server (validate AAR findings)
3. Integrate into CI (Phase 3)
4. Iterate based on real-world usage

---

**Status:** Ready for implementation  
**Owner:** TBD (assign to MCP team)  
**Timeline:** Phase 1-3 completable in 1 week with focused effort
