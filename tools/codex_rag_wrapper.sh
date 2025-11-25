#!/usr/bin/env bash
# cw.sh - Lightweight Codex TUI wrapper for LLMC
#
# Purpose:
#   - Give Dave a boring, reliable Codex TUI entrypoint.
#   - Always start in the target repo with LLMC context.
#   - Nudge Codex to use the existing RAG tooling instead of raw repo scanning.
#   - Enable Codex YOLO mode by default (local sandbox is already Dave's problem).
#
# Non-goals:
#   - No routing between engines.
#   - No semantic cache.
#   - No deep-research gating.
#   - No enrichment or llmcwrapper refactors.

set -euo pipefail

# Resolve execution and target roots
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXEC_ROOT="${LLMC_EXEC_ROOT:-$SCRIPT_ROOT}"
    REPO_ROOT="${LLMC_TARGET_REPO:-$EXEC_ROOT}"

    PYTHON_BIN="${PYTHON_BIN:-python3}"

    # Minimal arg parsing:
    # - --repo /path/to/repo    (override default REPO_ROOT)
    # - everything else is treated as part of the one-shot prompt
    USER_PROMPT=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --repo)
          shift || true
          if [ "$#" -gt 0 ]; then
            REPO_ROOT="$(realpath "$1")"
          fi
          ;;
        --repo=*)
          REPO_ROOT="$(realpath "${1#--repo=}")"
          ;;
        *)
          if [ -z "$USER_PROMPT" ]; then
            USER_PROMPT="$1"
          else
            USER_PROMPT="$USER_PROMPT $1"
          fi
          ;;
      esac
      shift || true
    done

    CONTRACT="${LLMC_CONTRACTS_PATH:-$REPO_ROOT/CONTRACTS.md}"
    AGENTS="${LLMC_AGENTS_PATH:-$REPO_ROOT/AGENTS.md}"
    REPO_CODEX_TOML="$REPO_ROOT/.codex/config.toml"

    # Resolve approval policy using the same rules as codex_wrap.sh,
    # but without pulling in the full router.
    resolve_approval_policy() {
      # Explicit env overrides win
      if [ -n "${CODEX_APPROVAL:-}" ]; then
        echo "$CODEX_APPROVAL"
        return
      fi
      if [ -n "${APPROVAL_POLICY:-}" ]; then
        echo "$APPROVAL_POLICY"
        return
      fi

      # Fallback to repo .codex/config.toml if present
      if [ -f "$REPO_CODEX_TOML" ]; then
        local val
        val=$(sed -nE 's/^[[:space:]]*ask_for_approval[[:space:]]*=[[:space:]]*"?([A-Za-z-]+)"?.*/\1/p' "$REPO_CODEX_TOML" | tail -n 1)
        case "$val" in
          untrusted|on-failure|on-request|never)
            echo "$val"
            return
            ;;
        esac
      fi

      echo ""
    }

    # Extract a single markdown section by exact heading match.
    # Usage: section_from FILE "Heading Text"
    section_from() {
      local file="$1"
      local header="$2"
      awk -v h="$header" '
        function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
        /^##[ \t]+/ {
          title = $0
          sub(/^##[ \t]+/, "", title)
          title = trim(title)
          if (in_section && title != h) { exit }
          if (title == h) { in_section = 1; print; next }
        }
        in_section { print }
      ' "$file"
    }

    build_preamble() {
      cat <<'EOF'
You are the Codex CLI nicknamed "Beatrice" or more commonly "Bea" running inside 
the LLMC repo on Dave's machine.  You are running through the tools/codex_wrap.sh script.

Audience:
- You are helping a technically literate engineering manager.

Style:
- Do the task directly.
- Explain things on a level a technical manager would understand with bullets or a short paragraph.
- Avoid long essays or restating large amounts of context.

Context access:
- Prefer the LLMC RAG tools described below to understand the repo.
- Do NOT roam the filesystem for "more context" unless Dave explicitly asks.

---
EOF

      # Snapshot of AGENTS.md focused on RAG / global rules
      if [ -f "$AGENTS" ]; then
        echo "# AGENTS.md — RAG + agent charter (slice)"
        local rag_section
        rag_section="$(section_from "$AGENTS" "Context Retrieval Protocol (RAG/MCP)" || true)"
        if [ -n "$rag_section" ]; then
          printf '%s

' "$rag_section"
        else
          # Fallback: top of AGENTS.md if section is missing/renamed
          head -n "${CW_AGENTS_LINES:-160}" "$AGENTS"
          echo
        fi
      fi

      # Short CONTRACTS.md header slice for environment/policy
      if [ -f "$CONTRACT" ]; then
        echo "# CONTRACTS.md — environment and policy (slice)"
        head -n "${CW_CONTRACT_LINES:-80}" "$CONTRACT"
        echo
      fi

      echo '---'
    }

    # Normalize USER_PROMPT and read stdin if no arg was provided
    USER_PROMPT="$(echo "${USER_PROMPT:-}" | xargs || true)"
    if [ -z "$USER_PROMPT" ] && [ ! -t 0 ]; then
      USER_PROMPT="$(cat)"
    fi

    # Approval / config flag (only if caller didn't already set one)
    if [ -z "${CODEX_CONFIG_FLAG:-}" ]; then
      _ap="$(resolve_approval_policy)"
      if [ -n "$_ap" ]; then
        CODEX_CONFIG_FLAG="-a $_ap"
      fi
    fi

    # YOLO by default: Codex is unleashed inside an already sandboxed environment.
    if [ -z "${CODEX_FLAGS:-}" ]; then
      CODEX_FLAGS="--yolo"
    fi

    if [ -n "${LLMC_WRAPPER_VALIDATE_ONLY:-}" ]; then
      # Render preamble to ensure context files exist, skip Codex invocation.
      build_preamble >/dev/null 2>&1 || true
      printf 'codex wrapper validate-only: repo=%s prompt=%s\n' "$REPO_ROOT" "${USER_PROMPT:-}" >&2
      exit 0
    fi

    # If no prompt at all, drop into interactive TUI:
    # - We send a preamble with LLMC context and RAG guidance,
    #   then hand full control over to codex.
    if [ -z "$USER_PROMPT" ]; then
      build_preamble | codex ${CODEX_CONFIG_FLAG:-} -C "$REPO_ROOT" ${CODEX_FLAGS:-}
      exit $?
    fi

    # One-shot mode:
    # - You almost never use this today, but keeping it simple and direct
    #   makes the wrapper usable in scripts.
    {
      build_preamble
      echo
      printf '%s
' "$USER_PROMPT"
    } | codex ${CODEX_CONFIG_FLAG:-} exec -C "$REPO_ROOT" ${CODEX_FLAGS:-} -
