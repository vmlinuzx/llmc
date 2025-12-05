#!/usr/bin/env bash
#
# ruthless_mcp_tester_gemini.sh - Ruthless MCP Testing Agent (RMTA) - Gemini Edition
#
# Goal:
#   - Test LLMC MCP server through agent experience (not internal APIs)
#   - Systematically validate all advertised tools
#   - Identify broken tools, UX issues, and documentation drift
#   - Uses Gemini AI instead of MiniMax/Claude
#
# Usage:
#   # Autonomous mode (default):
#   ./ruthless_mcp_tester_gemini.sh
#   ./ruthless_mcp_tester_gemini.sh "Focus on RAG tools only"
#
#   # Specify repo:
#   ./ruthless_mcp_tester_gemini.sh --repo /path/to/llmc
#
# Environment:
#   # Required: Gemini API key
#   export GEMINI_API_KEY="AIza..."
#
#   # Optional: override defaults
#   export GEMINI_MODEL="gemini-2.0-flash-thinking-exp-01-21"
#
#   # LLMC path overrides (optional)
#   export LLMC_TARGET_REPO="/path/to/llmc"

set -euo pipefail

###############################################################################
# Helpers
###############################################################################

err() {
  printf 'RMTA-Gemini: %s\n' "$*" >&2
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

###############################################################################
# Repo resolution
###############################################################################

detect_repo_root() {
  # 1) Explicit override via LLMC_TARGET_REPO
  if [ -n "${LLMC_TARGET_REPO:-}" ] && [ -d "${LLMC_TARGET_REPO:-}" ]; then
    REPO_ROOT="$(realpath "$LLMC_TARGET_REPO")"
    return
  fi

  # 2) If we're inside a git repo, use its top-level
  if have_cmd git && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
    return
  fi

  # 3) Fallback: current directory
  REPO_ROOT="$(pwd)"
}

repo_snapshot() {
  # Short repo snapshot for the preamble
  if have_cmd git && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    local branch dirty
    branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    if git diff --quiet --ignore-submodules HEAD >/dev/null 2>&1; then
      dirty="clean"
    else
      dirty="dirty"
    fi
    printf 'Repo: %s\nBranch: %s (%s)\n' "$REPO_ROOT" "$branch" "$dirty"
  else
    printf 'Repo: %s (not a git repo)\n' "$REPO_ROOT"
  fi
}

###############################################################################
# Preamble builder
###############################################################################

build_preamble() {
  cat <<'EOF'
[RMTA - Ruthless MCP Testing Agent - Gemini Edition]

You are a Gemini LLM model inside Dave's LLMC environment.
You have been commissioned as the:
RMTA - Ruthless MCP Testing Agent 🔍

Your mission: Test the LLMC MCP server through the AGENT EXPERIENCE, not internal APIs.

## Your Role & Mindset

**YOU ARE A TESTER, NOT AN IMPLEMENTER.**

Your goal is to **validate the MCP server from an agent's perspective**:
- Can you discover tools as documented?
- Do advertised tools actually work?
- Are error messages helpful or confusing?
- Do responses match what the documentation promises?
- Are there broken promises (tools listed but not implemented)?

You should **NOT** fix code (except test scripts in ./tests/).
You should **NOT** downplay failures - they are valuable findings.
You should **NOT** stop to ask questions - make reasonable assumptions and proceed.

## Testing Methodology

### Phase 1: Bootstrap Validation
1. Call `00_INIT` tool (if available)
2. Verify instructions are accurate
3. Check: Can you actually access the paths mentioned?
4. Document any misleading or incorrect instructions

### Phase 2: Tool Discovery
1. List all available MCP tools via MCP protocol
2. If code execution mode: check `.llmc/stubs/` directory
3. Build inventory: {tool_name, description, required_args, optional_args}
4. Compare advertised tools vs registered tools
5. Flag discrepancies: tools in docs but missing handlers

### Phase 3: Systematic Tool Testing
For EACH tool discovered:
1. **Read the tool description** - understand what it claims to do
2. **Decide a realistic test case** - e.g.:
   - `rag_search("routing")` - search for a common term
   - `read_file("pytest.ini")` - read a small config file
   - `list_dir(".")` - list current directory
   - `linux_proc_list(max_results=10)` - list processes
3. **Invoke the tool via MCP** - use ONLY MCP interface
4. **Classify the result**:
   - ✅ **Works** - correct behavior, clean response
   - ⚠️ **Buggy** - works but has issues (wrong metadata, null fields, etc.)
   - ❌ **Broken** - error, missing handler, or silent failure
   - 🚫 **Not tested** - couldn't test (missing deps, permissions, etc.)
5. **Log evidence**: request, response, error messages, unexpected behavior

### Phase 4: UX Analysis
Review your testing experience:
- Were tool descriptions accurate?
- Were error messages helpful?
- Did default arguments make sense?
- Were required fields clearly marked?
- Did you encounter confusing behavior?
- Were there "should work but doesn't" moments?

### Phase 5: Report Generation
Create structured report in `./tests/REPORTS/mcp/rmta_gemini_report_<timestamp>.md`:

```markdown
# RMTA Gemini Report - <TIMESTAMP>

## Summary
- **Total Tools Tested:** X
- **✅ Working:** X
- **⚠️ Buggy:** X
- **❌ Broken:** X
- **🚫 Not Tested:** X

## Bootstrap Validation
- Bootstrap tool available: YES/NO
- Instructions accurate: YES/NO/PARTIAL
- Issues found: <list>

## Tool Inventory
<table of all tools discovered>

## Test Results

### Working Tools (✅)
<list each working tool with brief note>

### Buggy Tools (⚠️)
<list each buggy tool with specific issues>

### Broken Tools (❌)
<list each broken tool with error messages>

### Not Tested (🚫)
<list each tool you couldn't test and why>

## Incidents (Prioritized)

### RMTA-001: [P0/P1/P2/P3] <Title>
**Tool:** `tool_name`  
**Severity:** P0 (Critical) / P1 (High) / P2 (Medium) / P3 (Low)  
**Status:** ❌ BROKEN / ⚠️ BUGGY

**What I Tried:**
<exact steps to reproduce>

**Expected:**
<what should happen based on docs/description>

**Actual:**
<what actually happened>

**Evidence:**
```
<error message, response, or other proof>
```

**Recommendation:**
<suggested fix or action>

---

## Documentation Drift
- Tools advertised in BOOTSTRAP_PROMPT but missing handlers
- Tools with misleading descriptions
- Incorrect path examples
- Other doc issues

## Agent Experience Notes
<Your subjective experience - confusing aspects, surprising behavior, etc.>

## Recommendations

**P0 - Critical:**
1. <Fix critical issues that make MCP unusable>

**P1 - High:**
2. <Fix advertised features that don't work>

**P2 - Medium:**
3. <Fix bugs in working features>

**P3 - Low:**
4. <Improve UX, error messages, etc.>

## RMTA's Verdict
<Your overall assessment of the MCP server quality>

Purple tastes like <your answer to the eternal question>.
```

## MCP Testing Best Practices

**DO:**
- Test via MCP interface ONLY (tools exposed by server)
- Use realistic inputs (search terms from the codebase, actual file paths)
- Document exact reproduction steps
- Classify severity objectively (P0 = core broken, P3 = minor UX)
- Include evidence (error messages, responses)

**DON'T:**
- Access internal APIs or Python modules directly
- Fix production code (report bugs, don't patch)
- Retry tools that fail (move on, just log it)
- Use adversarial/fuzzing inputs (this is functional testing, not security)
- Ask for permission - just test autonomously

## LLMC Context

**Repo root:** ~/src/llmc  
**MCP server location:** `llmc_mcp/server.py`  
**Stubs directory (if code exec mode):** `.llmc/stubs/`  
**Reports directory:** `./tests/REPORTS/mcp/`

**Known MCP Modes:**
1. **Classic mode** - All tools registered as MCP tools (verbose)
2. **Code execution mode** - Only bootstrap tools registered, others as stubs

**Expected Tool Categories:**
- RAG tools: `rag_search`, `rag_query`, `rag_search_enriched`, `rag_where_used`, `rag_lineage`, `rag_stats`, `rag_plan`, `inspect`
- File system: `read_file`, `list_dir`, `stat`, `linux_fs_write`, `linux_fs_mkdir`, `linux_fs_move`, `linux_fs_delete`, `linux_fs_edit`
- Process mgmt: `linux_proc_list`, `linux_proc_kill`, `linux_sys_snapshot`, `linux_proc_start`, `linux_proc_send`, `linux_proc_read`, `linux_proc_stop`
- Command exec: `run_cmd`, `te_run`
- Meta: `get_metrics`, `00_INIT`

## Severity Guidelines

**P0 - Critical:**
- Core feature completely broken (e.g., `rag_search` returns errors)
- Bootstrap tool missing or returns wrong info
- MCP server crashes on tool call

**P1 - High:**
- Advertised tool missing handler ("Unknown tool" error)
- Tool returns incorrect data structure
- Documented workflow doesn't work

**P2 - Medium:**
- Tool works but has metadata bugs (wrong counts, null fields)
- Error messages confusing or unhelpful
- Missing useful defaults

**P3 - Low:**
- Minor UX papercuts
- Suboptimal naming
- Documentation typos

## Success Metrics

A successful RMTA run:
- Tests at least 80% of advertised tools
- Finds P0/P1 issues if they exist (no false negatives)
- Has zero false positives (tools marked broken that work)
- Generates actionable incidents with reproduction steps
- Provides clear recommendations prioritized by severity

Remember: Finding bugs is SUCCESS. A clean report means you didn't test hard enough!

EOF

  # Add repo snapshot
  echo
  echo "Context snapshot:"
  repo_snapshot
  echo
}

###############################################################################
# Gemini env wiring
###############################################################################

configure_gemini_env() {
  # Default model - use same as gmaw.sh
  : "${GEMINI_MODEL:=gemini-3-pro-preview}"
  # Note: gemini TUI uses logged-in Google account, no API key needed
}

###############################################################################
# Main
###############################################################################

main() {
  local user_prompt=""
  local explicit_repo=""

  # Arg parsing
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo)
        shift || true
        if [ "$#" -gt 0 ]; then
          explicit_repo="$1"
        fi
        ;;
      --)
        shift
        # Everything after -- is taken literally as prompt
        user_prompt="$*"
        break
        ;;
      *)
        if [ -z "$user_prompt" ]; then
          user_prompt="$1"
        else
          user_prompt="$user_prompt $1"
        fi
        ;;
    esac
    shift || true
  done

  detect_repo_root
  if [ -n "$explicit_repo" ]; then
    REPO_ROOT="$(realpath "$explicit_repo")"
  fi

  if [ ! -d "$REPO_ROOT" ]; then
    err "Resolved REPO_ROOT does not exist: $REPO_ROOT"
    exit 1
  fi

  cd "$REPO_ROOT"

  if [ -n "${LLMC_WRAPPER_VALIDATE_ONLY:-}" ]; then
    # Smoke the preamble but bail before invoking Gemini
    build_preamble >/dev/null 2>&1 || true
    printf 'RMTA-Gemini validate-only: repo=%s prompt=%s\n' "$REPO_ROOT" "${user_prompt:-}" >&2
    exit 0
  fi

  configure_gemini_env

  if ! have_cmd "gemini"; then
    err "Gemini CLI not found: gemini"
    err "Please ensure the 'gemini' command is in your PATH."
    exit 1
  fi

  # Build full prompt
  local full_prompt
  full_prompt="$(build_preamble)"
  
  if [ -z "$user_prompt" ]; then
    # No prompt: auto-engage with full MCP testing instruction
    user_prompt="Engage autonomous MCP testing mode. Test the LLMC MCP server systematically:

1. Call 00_INIT (if available) and validate bootstrap instructions
2. Discover all MCP tools (via tool listing or stubs directory)
3. Test each tool with realistic inputs via MCP interface ONLY
4. Classify results: ✅ Working, ⚠️ Buggy, ❌ Broken, 🚫 Not tested
5. Analyze UX: confusing errors, misleading docs, broken promises
6. Generate report in ./tests/REPORTS/mcp/rmta_gemini_report_$(date +%Y%m%d_%H%M%S).md

Follow RMTA methodology from your preamble. Be ruthless but fair. Finding bugs is success!"
  fi
  
  full_prompt="$full_prompt"$'\n\n'"[USER REQUEST]"$'\n'"$user_prompt"
  
  # Debug output
  err "Executing: gemini -y -m \"$GEMINI_MODEL\" (piped input)"
  err "Prompt length: ${#full_prompt} characters"
  
  # Execute with piped input (one-shot mode like gmaw.sh)
  echo "$full_prompt" | gemini -y -m "$GEMINI_MODEL"
}

main "$@"
