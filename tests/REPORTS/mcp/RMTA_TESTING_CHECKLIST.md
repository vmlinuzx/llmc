# RMTA Testing Checklist

This checklist is embedded in the RMTA agent prompt to ensure systematic testing coverage.

## Pre-Flight

- [ ] Verify MCP server is running
- [ ] Check Claude CLI is available
- [ ] Confirm ANTHROPIC_AUTH_TOKEN is set
- [ ] Create report directory if needed

## Phase 1: Bootstrap Validation

- [ ] Call `00_INIT` tool (if available)
- [ ] Verify bootstrap instructions are accurate
- [ ] Check paths mentioned in instructions exist
- [ ] Validate tool list matches registered tools
- [ ] Document any misleading instructions

## Phase 2: Tool Discovery

- [ ] List all MCP tools via protocol
- [ ] If code exec mode: inspect `.llmc/stubs/` directory
- [ ] Build complete tool inventory with:
  - [ ] Tool name
  - [ ] Description
  - [ ] Required arguments
  - [ ] Optional arguments
  - [ ] Default values
- [ ] Compare advertised tools vs registered tools
- [ ] Flag discrepancies

## Phase 3: Systematic Tool Testing

For EACH tool in inventory:

### RAG Tools
- [ ] `rag_search` - Search for common term (e.g., "routing")
- [ ] `rag_query` - Query with realistic parameters
- [ ] `rag_search_enriched` - Test enrichment modes
- [ ] `rag_where_used` - Find symbol usage
- [ ] `rag_lineage` - Trace dependencies
- [ ] `rag_stats` - Get coverage statistics
- [ ] `rag_plan` - Analyze query routing
- [ ] `inspect` - Deep dive on file/symbol

### File System Tools
- [ ] `read_file` - Read small config file (e.g., "pytest.ini")
- [ ] `list_dir` - List current directory
- [ ] `stat` - Get file metadata
- [ ] `linux_fs_write` - Write to /tmp file
- [ ] `linux_fs_mkdir` - Create test directory
- [ ] `linux_fs_move` - Move test file
- [ ] `linux_fs_delete` - Delete test file
- [ ] `linux_fs_edit` - Edit text file (check `replacements_made`)

### Process Management Tools
- [ ] `linux_proc_list` - List top 10 processes
- [ ] `linux_proc_kill` - Send signal (test with safe PID)
- [ ] `linux_sys_snapshot` - Get system metrics
- [ ] `linux_proc_start` - Start simple REPL (e.g., `cat`)
- [ ] `linux_proc_send` - Send input to process
- [ ] `linux_proc_read` - Read process output
- [ ] `linux_proc_stop` - Stop process cleanly

### Command Execution Tools
- [ ] `run_cmd` - Execute safe command (e.g., `echo hello`)
- [ ] `te_run` - Execute via Tool Envelope

### Meta Tools
- [ ] `get_metrics` - Get MCP metrics (if observability enabled)
- [ ] `00_INIT` - Already tested in Phase 1

### Tool Repo Tools
- [ ] `repo_read` - Read file from repository

## Phase 4: Classification

For each tool tested, assign status:

- [ ] ✅ **Working** - Correct behavior, clean response
- [ ] ⚠️ **Buggy** - Works but has issues (metadata bugs, null fields)
- [ ] ❌ **Broken** - Error, missing handler, silent failure
- [ ] 🚫 **Not tested** - Couldn't test (missing deps, permissions)

## Phase 5: UX Analysis

Review testing experience:

- [ ] Were tool descriptions accurate?
- [ ] Were error messages helpful?
- [ ] Did default arguments make sense?
- [ ] Were required fields clearly marked?
- [ ] Any confusing behavior?
- [ ] Any "should work but doesn't" moments?

## Phase 6: Incident Documentation

For each issue found:

- [ ] Assign severity (P0 = Critical, P1 = High, P2 = Medium, P3 = Low)
- [ ] Document exact repro steps
- [ ] Capture evidence (error message, response, etc.)
- [ ] Describe expected vs actual behavior
- [ ] Provide recommendation

## Phase 7: Report Generation

- [ ] Summary table (tool counts)
- [ ] Bootstrap validation results
- [ ] Tool inventory
- [ ] Test results by status
- [ ] Prioritized incidents
- [ ] Documentation drift analysis
- [ ] Agent experience notes
- [ ] Recommendations (prioritized)
- [ ] Purple flavor verdict

## Expected Coverage

Minimum acceptable:
- **80%** of advertised tools tested
- **100%** of known P0/P1 issues detected (from AAR)
- **0%** false positives
- **100%** of incidents have repro steps

## Known Issues to Verify (from 2025-12-04 AAR)

### Must Detect (P1)
- [ ] `rag_where_used` - Missing handler
- [ ] `rag_lineage` - Missing handler
- [ ] `rag_stats` - Missing handler
- [ ] `inspect` - Missing handler

### Must Detect (P1) - Stubs
- [ ] `linux_proc_list` - Returns empty data
- [ ] `linux_sys_snapshot` - Returns N/A values
- [ ] `linux_proc_*` REPLs - All return empty

### Must Detect (P2) - Bugs
- [ ] `linux_fs_edit` - Incorrect `replacements_made` count
- [ ] `rag_query` - Some results have `summary: None`
- [ ] `stat` - Returns minimal metadata

### Should NOT Detect (Fixed)
- [ ] Bootstrap path examples (already fixed)

## Post-Run Validation

- [ ] Report saved to `tests/REPORTS/mcp/rmta_report_<timestamp>.md`
- [ ] Report follows template structure
- [ ] All incidents have P0-P3 severity
- [ ] All incidents have evidence
- [ ] Recommendations are prioritized
- [ ] False positive rate: 0%
- [ ] Coverage rate: ≥80%

## Success Definition

**RMTA run is successful if:**
1. ✅ Tests ≥80% of advertised tools
2. ✅ Finds all known P0/P1 issues from AAR
3. ✅ Zero false positives
4. ✅ Report includes actionable repro steps
5. ✅ Recommendations prioritized by severity

**Remember:** Finding bugs = SUCCESS. Perfect report = testing wasn't ruthless enough!
