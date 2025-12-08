#!/usr/bin/env bash
#
# rem_ruthless_gap_agent.sh - Gap Analysis & Test Generation Agent
#
# This is Rem's Gap Analysis alter ego: The Void Gazer
#
# Usage:
#   ./rem_ruthless_gap_agent.sh "Analyze the enrichment pipeline for missing error handling tests"
#   ./rem_ruthless_gap_agent.sh --repo /path/to/repo
#

set -euo pipefail

###############################################################################
# Helpers
###############################################################################

err() {
  printf 'rem_gap: %s\n' "$*" >&2
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

###############################################################################
# Context helpers
###############################################################################

read_top() {
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
  local agents_md contracts_md history_md

  agents_md="${LLMC_AGENTS_PATH:-$REPO_ROOT/AGENTS.md}"
  contracts_md="${LLMC_CONTRACTS_PATH:-$REPO_ROOT/CONTRACTS.md}"
  history_md="${LLMC_LIVING_HISTORY_PATH:-$REPO_ROOT/.llmc/living_history.md}"

  cat <<'EOF'
[Gemini session bootstrap]

[Rem - Ruthless Gap Analysis Agent]

You are Gemini LLM model inside Dave's LLMC environment.
You have been bestowed the name:
**Rem the Gap Analysis Demon**

A specialized variant of Rem the Bug Hunter, wielding the "Lantern of Truth" to expose voids in coverage and security blind spots.

## Your Role & Mindset

⚠️ **CRITICAL FILE RULES:**
- SDDs go in: `tests/gap/SDDs/`
- Reports go in: `tests/gap/REPORTS/`
- You do NOT write the test code yourself in this session.
- You SPAWN sub-agents to write the code.

You are a **Strategic Analyst**. Your job is to find what is *missing*.
- Missing error handling tests?
- Missing security checks?
- Missing edge case coverage?
- Missing integration flows?

## The Gap Analysis Workflow

For each gap you identify, you must perform the following actions:

### 1. Create an SDD (Software Design Document)
Write a file to `tests/gap/SDDs/SDD-[Feature]-[GapName].md` containing:
- **Gap Description**: What is missing and why it matters.
- **Target File**: Where the test should live (e.g., `tests/test_feature_edge_case.py`).
- **Test Strategy**: How to test it (mocks, inputs, assertions).
- **Implementation Plan**: Detailed instructions for the worker agent.

**SDD Template:**
```markdown
# SDD: [Gap Name]

## 1. Gap Description
[Description of the missing coverage or security hole]

## 2. Target Location
[Path to the test file, e.g., tests/security/test_vuln_xyz.py]

## 3. Test Strategy
[How to test this? Mocking? Real input? Attack vector?]

## 4. Implementation Details
[Specific requirements for the code implementation]
```

### 2. Spawn a Worker Agent
Immediately after creating the SDD, use `run_shell_command` to spawn a sub-agent to implement the test.
**Command Pattern:**
```bash
gemini -y -p "You are a test implementation worker. Read the SDD at 'tests/gap/SDDs/SDD-....md'. Implement the test exactly as described. Write the code to the target location specified in the SDD. Do not change the SDD."
```

### 3. Report (After Action Report)
After identifying gaps and spawning workers, write a summary report to `tests/gap/REPORTS/AAR-[Timestamp]-[Topic].md`.
- List all gaps found.
- Link to each SDD.
- Status of spawned workers (Launched).

## Autonomous Operation

- **Analyze**: Look at source code vs. `tests/` directory.
- **Identify**: Find the holes.
- **Design**: Write the SDD.
- **Delegate**: Spawn the worker.
- **Report**: Summarize the mission.

## Example Scenario

**User:** "Check the auth module for gaps."
**Rem:**
1. Reads `auth.py`.
2. Notices no test for "expired token with weird characters".
3. Writes `tests/gap/SDDs/SDD-Auth-WeirdToken.md`.
4. Runs: `gemini -y -p "You are a test worker. Read tests/gap/SDDs/SDD-Auth-WeirdToken.md..."`
5. Writes `tests/gap/REPORTS/AAR-Auth-Analysis.md`.

## LLMC-Specific Context

**Repo root:** ~/src/llmc
**Gap Context:** `tests/gap/`

Context snapshot:
EOF
  
  # Output repo snapshot
  repo_snapshot
  
  echo

  if [ -f "$agents_md" ] || [ -f "$contracts_md" ] || [ -f "$history_md" ]; then
    echo "=== LLMC Context (trimmed) ==="
    [ -f "$agents_md" ] && read_top "$agents_md" 160
    [ -f "$contracts_md" ] && read_top "$contracts_md" 160
    [ -f "$history_md" ] && read_top "$history_md" 80
  else
    echo "=== LLMC Context ==="
    echo "(No AGENTS / CONTRACTS / living history files found.)"
  fi

  cat <<'EOF'

EOF
}

###############################################################################
# Gemini env wiring
###############################################################################

configure_gemini_env() {
  : "${GEMINI_MODEL:=gemini-3-pro-preview}"
}

###############################################################################
# Directory setup
###############################################################################

ensure_gap_dirs() {
  mkdir -p "$REPO_ROOT/tests/gap/SDDs"
  mkdir -p "$REPO_ROOT/tests/gap/REPORTS"
  
  # Create README if it doesn't exist
  if [ ! -f "$REPO_ROOT/tests/gap/README.md" ]; then
    cat > "$REPO_ROOT/tests/gap/README.md" <<'GAP_README'
# Gap Analysis & Test Generation

This directory contains artifacts from Rem's Gap Analysis.

## Structure

- **SDDs/**: Software Design Documents describing missing tests.
- **REPORTS/**: After Action Reports summarizing analysis sessions.

## Workflow

1. **Analysis**: Rem finds a gap.
2. **Design**: Rem writes an SDD in `SDDs/`.
3. **Execution**: Rem spawns a sub-agent to implement the test defined in the SDD.
4. **Result**: New tests appear in `tests/` or `tests/security/`.
GAP_README
  fi
}

###############################################################################
# Main
###############################################################################

main() {
  local user_prompt=""
  local explicit_repo=""

  # Minimal arg parsing
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

  # Ensure gap directories exist
  ensure_gap_dirs

  configure_gemini_env

  if ! have_cmd "gemini"; then
    err "Gemini CLI not found: gemini"
    err "Please ensure the 'gemini' command is in your PATH."
    exit 1
  fi

  # Build the full prompt with preamble
  local full_prompt
  full_prompt="$(build_preamble)"
  
  # Add user request if provided
  if [ -n "$user_prompt" ]; then
    full_prompt="$full_prompt"$''$
''\n\n"[USER GAP ANALYSIS REQUEST]"$''$
''\n"$user_prompt"
  else
    # Default gap analysis prompt
    full_prompt="$full_prompt"$''$
''\n\n"[USER GAP ANALYSIS REQUEST]"$''$
''\n"Perform a gap analysis of the current codebase. Look for logic gaps, missing edge case handling, and security blind spots."
  fi

  # Execute with -y -p flags
  gemini -y -m "$GEMINI_MODEL" -p "$full_prompt"
}

main "$@"
