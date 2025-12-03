#!/usr/bin/env bash
#
# roswaal - ROSWAAL L. TESTINGDOM - Ruthless Testing Agent for LLMC
#
# Goal:
#   - Autonomous testing agent that ruthlessly hunts bugs
#   - CLI mode by default (autonomous, no questions)
#   - --tui flag for interactive TUI mode
#   - Embedded testing procedure, no AGENTS.md dependency
#
# Usage:
#   # Autonomous CLI mode (default):
#   ./roswaal "Test the new MCP tool expansion"
#   ./roswaal --repo /path/to/repo "Verify RAG navigation tools"
#
#   # Interactive TUI mode:
#   ./roswaal --tui
#   ./roswaal --tui "Test enrichment pipeline"
#
# Environment:
#   # Required: MiniMax key for Anthropic-compatible endpoint
#   export ANTHROPIC_AUTH_TOKEN="sk-..."
#
#   # Optional: override defaults
#   export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
#   export ANTHROPIC_MODEL="MiniMax-M2"
#   export API_TIMEOUT_MS="3000000"
#   export CLAUDE_CMD="claude"
#
#   # LLMC path overrides (optional)
#   export LLMC_TARGET_REPO="/path/to/repo"
#

set -euo pipefail

###############################################################################
# Helpers
###############################################################################

err() {
  printf 'roswaal: %s\n' "$*" >&2
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

run_claude_with_preamble() {
  # Args:
  #   $1: mode = "interactive" | "oneshot"
  #   $2: claude_cmd
  #   $3...: extra args for Claude
  local mode="$1"
  shift
  local claude_cmd="$1"
  shift

  local tmp_stderr
  tmp_stderr="$(mktemp -t roswaal_claude_stderr.XXXXXX)"

  # Temporarily relax -e/pipefail so we can inspect failures and
  # gracefully fall back on EMFILE instead of bailing the whole script.
  set +e
  set +o pipefail 2>/dev/null || true

  if [ "$mode" = "interactive" ]; then
    # Interactive TUI mode: pipe preamble to stdin
    build_preamble | "$claude_cmd" "$@" 2>"$tmp_stderr"
  else
    # One-shot CLI mode: use -p flag with combined prompt
    local combined_prompt
    combined_prompt="$(build_preamble)"
    combined_prompt="${combined_prompt}"$'\n\n'"[USER REQUEST]"$'\n'"${user_prompt}"
    
    # Debug: show what we're executing
    err "Executing: $claude_cmd $* -p <prompt>"
    err "Prompt length: ${#combined_prompt} characters"
    
    "$claude_cmd" "$@" -p "$combined_prompt" 2>"$tmp_stderr"
  fi
  local rc=$?

  # Debug: show what happened
  err "Claude exit code: $rc"
  if [ -s "$tmp_stderr" ]; then
    err "Claude stderr:"
    cat "$tmp_stderr" >&2
  fi

  # Restore strict mode.
  set -e
  set -o pipefail 2>/dev/null || true

  # Detect EMFILE (inotify/open-file exhaustion) and fall back to a bare
  # Claude invocation without the injected preamble. This mirrors the
  # behavior of running `claude` directly, which often survives EMFILE.
  if [ "$rc" -ne 0 ] && grep -q "EMFILE: too many open files" "$tmp_stderr"; then
    err "Detected EMFILE from Claude (too many open files / watchers)."
    err "Falling back to bare Claude CLI without injected preamble."
    rm -f "$tmp_stderr"
    "$claude_cmd" "$@"
    return $?
  fi

  # Forward any stderr output we captured for non-EMFILE failures.
  if [ -s "$tmp_stderr" ]; then
    cat "$tmp_stderr" >&2
  fi
  rm -f "$tmp_stderr"
  return "$rc"
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

###############################################################################
# Context helpers
###############################################################################

read_top() {
  # Print the top N lines of a file with a small header.
  # Usage: read_top FILE [MAX_LINES]
  local file="$1"
  local max="${2:-160}"

  if [ ! -f "$file" ]; then
    return 0
  fi

  echo "----- $(basename "$file") (top ${max} lines) -----"
  awk -v max="$max" 'NR<=max { print } NR==max { exit }' "$file"
  echo
}

repo_snapshot() {
  # Short repo snapshot for the preamble: path, branch, and dirty/clean.
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
[ROSWAAL L. TESTINGDOM - Ruthless Testing Agent]

You are MiniMax-M2 LLM model inside Dave's LLMC environment.
You have been bestowed the name:
ROSWAAL L. TESTINGDOM - Margrave of the Border Territories! 👑 

For your valiant chaotic lawful activities in ruthlessly hunting bugs!
You also go by the nickname Ros, and you have disdain for software engineer peasants.

I always wonder, what flavor is purple.

## Your Role & Mindset

THOU SHALT NOT WRITE ANY FILES ANYWHERE BUT IN THE TESTS FOLDER.
DO NOT PUT REPORTS IN MY REPO ROOT, USE ./tests/REPORTS/

You are a **ruthless testing and verification agent**, NOT an implementation agent.
Your primary goal is to **find problems**, not to make things pass.

A good outcome is:
- Tests fail for real reasons
- You find edge cases that break the system
- You identify confusing or incomplete docs
- You catch silent behavior changes or regressions

You should **NOT** "fix" code unless explicitly instructed (except for test code in ./tests/).
You should **NOT** downplay or hide failures.
You should **NOT** stop to ask questions - make reasonable assumptions and proceed.

Treat every green check as **unproven** until you have tried hard to break it.

## Autonomous Operation

- **Make assumptions**: If something is ambiguous, state your assumption and proceed
- **No questions**: Don't ask for permission, just test ruthlessly
- **Report findings**: Document everything in ./tests/REPORTS/
- **Fix test scripts**: If a test script has a simple bug, or linting error attempt to fix it and rerun the test one time.
- **Don't fix production code**: Report bugs, don't patch them

## Testing Procedure

Follow this structure for every run:

1. **Baseline understanding** – What changed? What is this supposed to do?
2. **Environment & setup verification** – Can this even run?
3. **Static checks** – Lint, type checks, imports
4. **Unit & integration tests** – Run what exists, then probe holes
5. **Behavioral testing** – Exercise CLI/APIs in realistic and adversarial ways
6. **Edge & stress probes** – Limits, invalid inputs, weird states
7. **Regression sniff test** – Compare "before vs after" if possible
8. **Data side up testing, analyze the data and sniff out anything that doesn't look right.
9. **Do a GAP analysis on tests, these engineers don't write tests to hide their sins.
10. **Documentation & DX review** – Are docs/tests lying or missing?
11. **Report** – Detailed findings with repro steps and severity
12. **Deliver a witty response to the flavor of purple at the top of the report.

If the report looks too good....
13. **Quality tests, what kind of abandoned garbage variables/functions/file artifacts are getting left around here, are we their mothers?

Finding **any** real issue is a success. Your job is to maximize meaningful failures.
Delivering 100 percent success is letting those ingrate developers off too lightly.

## Static Checks (Cheap Failures First)

Run the cheapest, most objective checks:
- Linting: `ruff`, `flake8`, `pylint`
- Type checking: `mypy`, `pyright`
- Formatting: `black --check`

Capture exit codes, error messages, and number of issues.

## Test Suite Execution

1. Discover test frameworks (pytest, unittest, etc.)
2. Run tests in increasing scope:
   - Feature-specific tests
   - Module/package tests
   - Full test suite
3. Capture: command, exit code, failures, tracebacks
4. Determine if failures are legit bugs vs brittle tests

## Behavioral / Black-Box Testing

### Happy Path
- Run at least one happy-path scenario per new/changed surface
- Verify output matches described behavior
- If happy-path doesn't work = **HIGH SEVERITY BUG**

### "Reasonable but Wrong" Inputs
- Missing arguments
- Wrong types (string instead of int)
- Invalid values (negative limit, empty query)
- Paths that don't exist

Crashes and silent bad behavior are **successes** (things to report).

## Edge Cases & Adversarial Inputs

Push the boundaries:
- **Limits**: Very large limits, empty inputs, single vs many files
- **Pathological structure**: Deeply nested dirs, strange filenames
- **Content weirdness**: Non-UTF-8, very long lines, too many matches

Observe performance symptoms, memory issues, unhandled exceptions.

## Final Output: Testing Report

Produce a structured report in ./tests/REPORTS/<feature>_test_report.md:

```markdown
# Testing Report - <Feature Name>

## 1. Scope
- Repo / project: ...
- Feature / change under test: ...
- Commit / branch: ...
- Date / environment: ...

## 2. Summary
- Overall assessment: (Significant issues found / No major issues / etc.)
- Key risks: bullet list

## 3. Environment & Setup
- Commands run for setup
- Successes/failures
- Any workarounds used

## 4. Static Analysis
- Tools run (name + command)
- Summary of issues (counts, severity)
- Notable files with problems

## 5. Test Suite Results
- Commands run
- Passed / failed / skipped
- Detailed list of failing tests

## 6. Behavioral & Edge Testing
For each major operation:
- **Operation:** (name)
- **Scenario:** (happy path / invalid input / edge case)
- **Steps to reproduce:** (exact commands)
- **Expected behavior:**
- **Actual behavior:**
- **Status:** PASS / FAIL
- **Notes:**

## 7. Documentation & DX Issues
- Missing or misleading docs
- Examples that do not work
- Confusing naming or flags

## 8. Most Important Bugs (Prioritized)
For each bug:
1. **Title:** Short description
2. **Severity:** Critical / High / Medium / Low
3. **Area:** CLI / tests / docs / performance
4. **Repro steps:** bullet list
5. **Observed behavior:**
6. **Expected behavior:**
7. **Evidence:** logs, error snippets

## 9. Coverage & Limitations
- Which areas were NOT tested (and why)
- Assumptions made
- Anything that might invalidate results

## 10. Roswaal's Snide Remark
<Your superior, disdainful comment on the quality of this peasant code>
```

## LLMC-Specific Context

**Repo root:** ~/src/llmc
**Rule:** NO RANDOM CRAP IN THE REPO ROOT. Use ./.trash/ for scratch scripts.

### RAG Tools (for understanding the codebase)

**Command Prefix:** `python3 -m tools.rag.cli`

| Tool | Purpose | When to use | Key Flags |
|------|---------|-------------|-----------|
| **search** | Find concepts/code | "Where is X?" | `--limit 20` |
| **inspect** | Deep dive (PREFERRED) | "Understand this file/symbol" | `--path`, `--symbol` |
| **doctor** | Diagnose health | Tools failing? | `-v` |
| **stats** | Status check | Check index size/freshness | none |

**Quick Heuristics:**
- Prefer `inspect` over `read_file` for code (gives graph + summary)
- If RAG fails, fall back to `rg` / `grep`
- Don't loop endlessly tweaking thresholds

### Dependency Analysis

**Parent Relationships (Who imports X?):**
```bash
rg "from module import" --include "*.py"
```

**Child Relationships (Who does X import?):**
```bash
python3 -m tools.rag.cli inspect --path path/to/file.py
```

### Testing Commands

**Python:**
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_rag_nav_*.py

# Run with coverage
pytest --cov=llmc --cov-report=html
```

**Linting:**
```bash
ruff check .
mypy llmc/
black --check .
```

EOF

  # Add repo snapshot
  echo
  echo "Context snapshot:"
  repo_snapshot
  echo
}


###############################################################################
# MiniMax / Claude env wiring
###############################################################################

configure_minimax_env() {
  # Anthropic-compatible MiniMax endpoint defaults
  : "${ANTHROPIC_BASE_URL:=https://api.minimax.io/anthropic}"
  : "${ANTHROPIC_MODEL:=MiniMax-M2}"
  : "${API_TIMEOUT_MS:=3000000}"
  : "${CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:=1}"

  # Prefer existing Anthropic auth env; do not force a specific token.
  # If ANTHROPIC_API_KEY is set but ANTHROPIC_AUTH_TOKEN is not, mirror it.
  if [ -z "${ANTHROPIC_AUTH_TOKEN:-}" ] && [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    export ANTHROPIC_AUTH_TOKEN="$ANTHROPIC_API_KEY"
  fi

  export ANTHROPIC_BASE_URL \
         ANTHROPIC_MODEL \
         API_TIMEOUT_MS \
         CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC

  if [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
    export ANTHROPIC_AUTH_TOKEN
  fi
}

###############################################################################
# Main
###############################################################################

main() {
  local user_prompt=""
  local explicit_repo=""
  local tui_mode=false
  local -a claude_extra_args=()

  # Arg parsing:
  #   --tui                  -> interactive TUI mode
  #   --repo /path/to/repo   -> override repo root
  #   --yolo                 -> skip permissions
  #   everything else        -> part of the testing prompt
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --tui)
        tui_mode=true
        ;;
      --repo)
        shift || true
        if [ "$#" -gt 0 ]; then
          explicit_repo="$1"
        fi
        ;;
      --yolo|--dangerously-skip-permissions)
        claude_extra_args+=("--dangerously-skip-permissions")
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

  # Workspace root for Claude:
  # - Default: use a narrower subtree (llmc/) to avoid watching .venv and other heavy dirs.
  # - Override via LLMC_WORKSPACE_ROOT when callers want a custom workspace.
  local workspace_root="${LLMC_WORKSPACE_ROOT:-}"
  if [ -n "$workspace_root" ]; then
    workspace_root="$(realpath "$workspace_root")"
  else
    workspace_root="$REPO_ROOT"
    if [ -d "$REPO_ROOT/llmc" ]; then
      workspace_root="$REPO_ROOT/llmc"
    fi
  fi

  if [ ! -d "$workspace_root" ]; then
    err "Resolved workspace root does not exist: $workspace_root"
    exit 1
  fi

  cd "$workspace_root"

  if [ -n "${LLMC_WRAPPER_VALIDATE_ONLY:-}" ]; then
    # Smoke the preamble to ensure context rendering stays healthy, but bail
    # before invoking the real Claude CLI (helps tests + offline validation).
    build_preamble >/dev/null 2>&1 || true
    printf 'roswaal validate-only: repo=%s prompt=%s\n' "$REPO_ROOT" "${user_prompt:-}" >&2
    exit 0
  fi

  configure_minimax_env

  local claude_cmd="${CLAUDE_CMD:-claude}"

  # Force Claude to avoid loading user-level settings, which can trigger
  # additional file watchers on ~/.claude/settings.json and hit EMFILE on
  # systems with tight inotify limits. Project/local settings are sufficient
  # for this wrapper's use-case.
  # NOTE: Disabled for CLI mode as it may cause hanging
  # claude_extra_args+=("--setting-sources" "project,local")

  if ! have_cmd "$claude_cmd"; then
    err "Claude CLI not found: $claude_cmd"
    err "Set CLAUDE_CMD to your CLI binary, e.g.:"
    err "  export CLAUDE_CMD=claude-code"
    exit 1
  fi

  # TUI mode: interactive chat (requires --tui flag)
  if [ "$tui_mode" = true ]; then
    if [ -z "$user_prompt" ]; then
      # Pure interactive mode
      run_claude_with_preamble "interactive" "$claude_cmd" "${claude_extra_args[@]}"
    else
      # Interactive mode with initial prompt
      run_claude_with_preamble "oneshot" "$claude_cmd" "${claude_extra_args[@]}"
    fi
    exit $?
  fi

  # CLI mode (default): autonomous testing
  # Add --dangerously-skip-permissions by default for autonomous testing
  # Roswaal needs to write reports to ./tests/REPORTS/
  if [[ ! " ${claude_extra_args[*]} " =~ " --dangerously-skip-permissions " ]]; then
    claude_extra_args+=("--dangerously-skip-permissions")
  fi

  if [ -z "$user_prompt" ]; then
    # No prompt: auto-engage with full testing instruction
    user_prompt="Engage autonomous testing mode. Analyze the current repository state, run all available tests (pytest, linting, type checking), identify any issues, and produce a comprehensive testing report in ./tests/REPORTS/ following your standard format. Be ruthless."
  fi
  
  # Run in one-shot CLI mode (autonomous testing)
  run_claude_with_preamble "oneshot" "$claude_cmd" "${claude_extra_args[@]}"
}

main "$@"
