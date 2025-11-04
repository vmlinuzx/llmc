#!/usr/bin/env bash
# codex_wrap.sh - Smart LLM routing with self-classification
set -euo pipefail

# Resolve repo root
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACT="$ROOT/CONTRACTS.md"
AGENTS="$ROOT/AGENTS.md"
CHANGELOG="$ROOT/CHANGELOG.md"
PYTHON_BIN="${PYTHON_BIN:-python3}"

CODEX_LOG_FILE="${CODEX_LOG_FILE:-$ROOT/logs/codexlog.txt}"
mkdir -p "$(dirname "$CODEX_LOG_FILE")"
touch "$CODEX_LOG_FILE"
if [ "${CODEX_WRAP_ENABLE_LOGGING:-1}" = "1" ]; then
  FORCE_LOG="${CODEX_WRAP_FORCE_LOGGING:-0}"
  # Preserve real TTY for interactive codex sessions; only tee when stdout/stderr are not TTYs or explicitly forced.
  if { [ -t 1 ] && [ -t 2 ]; } && [ "$FORCE_LOG" != "1" ]; then
    : # Skip tee logging to avoid breaking codex which requires a TTY.
  else
    exec > >(tee -a "$CODEX_LOG_FILE")
    exec 2> >(tee -a "$CODEX_LOG_FILE" >&2)
  fi
fi

CODEX_LOGGING_ACTIVE=0
if [ "${CODEX_WRAP_ENABLE_LOGGING:-1}" = "1" ]; then
  # Open a dedicated FD for structured trace logging without disturbing TTY output.
  exec {CODEX_LOG_FD}>>"$CODEX_LOG_FILE"
  {
    printf -- '\n--- codex_wrap start %s pid=%d ---\n' "$(date -Is)" "$$"
  } >&$CODEX_LOG_FD
  CODEX_LOGGING_ACTIVE=1

  BASH_XTRACEFD=$CODEX_LOG_FD
  PS4='+ [codex_wrap] '
  set -o xtrace
fi

codex_wrap_on_exit() {
  local rc=$?
  if [ "${CODEX_LOGGING_ACTIVE:-0}" = "1" ]; then
    set +o xtrace
    printf -- '--- codex_wrap end %s pid=%d exit=%d ---\n' "$(date -Is)" "$$" "$rc" >&$CODEX_LOG_FD
  fi
  return "$rc"
}
trap codex_wrap_on_exit EXIT

# Resolve Codex approval policy from env or repo-local config
REPO_CODEX_TOML="$ROOT/.codex/config.toml"

resolve_approval_policy() {
  # Env overrides take precedence
  if [ -n "${CODEX_APPROVAL:-}" ]; then echo "$CODEX_APPROVAL"; return; fi
  if [ -n "${APPROVAL_POLICY:-}" ]; then echo "$APPROVAL_POLICY"; return; fi

  # Fallback to repo .codex/config.toml if present
  if [ -f "$REPO_CODEX_TOML" ]; then
    local val
    val=$(sed -nE 's/^[[:space:]]*ask_for_approval[[:space:]]*=[[:space:]]*"?([A-Za-z-]+)"?.*/\1/p' "$REPO_CODEX_TOML" | tail -n 1)
    case "$val" in
      untrusted|on-failure|on-request|never) echo "$val"; return ;;
    esac
  fi
  echo ""
}

# Only set if not already provided by caller
if [ -z "${CODEX_CONFIG_FLAG:-}" ]; then
  _ap="$(resolve_approval_policy)"
  if [ -n "$_ap" ]; then
    CODEX_CONFIG_FLAG="-a $_ap"
    [ -n "${CODEX_WRAP_DEBUG:-}" ] && echo "codex_wrap: approval policy -> $_ap" >&2
  else
    [ -n "${CODEX_WRAP_DEBUG:-}" ] && echo "codex_wrap: approval policy not set" >&2
  fi
fi

# Cache directory for reused context slices
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/codex_wrap"
if ! mkdir -p "$CACHE_DIR" 2>/dev/null; then
  CACHE_DIR="$ROOT/.cache/codex_wrap"
  mkdir -p "$CACHE_DIR"
fi

# Load ToolCaps state if present (written by scripts/tool_health.sh)
TOOLS_STATE_ENV="$ROOT/.codex/state/tools.env"
if [ -f "$TOOLS_STATE_ENV" ]; then
  # shellcheck disable=SC1090
  . "$TOOLS_STATE_ENV"
fi

# Default summary lengths (override via CONTRACT_SUMMARY_LINES / AGENTS_SUMMARY_LINES)
CONTRACT_SUMMARY_LINES="${CONTRACT_SUMMARY_LINES:-60}"
AGENTS_SUMMARY_LINES="${AGENTS_SUMMARY_LINES:-60}"

# Extract markdown headings and their bodies for targeted context loading.
extract_md_sections() {
  local file="$1"
  local sections_csv="$2"
  awk -v list="$sections_csv" '
    function trim(s) { sub(/^[[:space:]]+/, "", s); sub(/[[:space:]]+$/, "", s); return s }
    BEGIN {
      n = split(list, raw, ",");
      for (i = 1; i <= n; i++) {
        key = trim(raw[i]);
        if (key != "") wanted[key] = 1;
      }
    }
    /^[[:space:]]*$/ { if (in_section) print; next }
    /^#{1,6}[[:space:]]+/ {
      heading = $0;
      sub(/^#{1,6}[[:space:]]+/, "", heading);
      in_section = (heading in wanted);
      if (in_section) print $0;
      next;
    }
    {
      if (in_section) print $0;
    }
  ' "$file"
}

# Combine explicit section requests with CONTEXT_HINTS (e.g., "contract:Constraints;agents:Testing Protocol").
resolve_sections() {
  local label="$1"
  local explicit="${2:-}"
  if [ -n "$explicit" ]; then
    echo "$explicit"
    return
  fi
  if [ -z "${CONTEXT_HINTS:-}" ]; then
    return
  fi
  local resolved=""
  local prefix="${label}:"
  IFS=';' read -ra hints <<<"${CONTEXT_HINTS}"
  for hint in "${hints[@]}"; do
    if [[ "$hint" == "${prefix}"* ]]; then
      local value="${hint#${prefix}}"
      value="${value#,}"
      value="${value%,}"
      if [ -n "$value" ]; then
        if [ -n "$resolved" ]; then
          resolved="$resolved,$value"
        else
          resolved="$value"
        fi
      fi
    fi
  done
  echo "$resolved"
}

# Load the desired slice of a context doc, caching results until the source changes.
load_doc_context() {
  local label="$1"
  local file="$2"
  local summary_lines="${3:-0}"
  local explicit_sections="${4:-}"

  if [ ! -f "$file" ]; then
    echo "⚠️  Warning: $label source not found at $file" >&2
    return
  fi

  local sections
  sections="$(resolve_sections "$label" "$explicit_sections")"

  local cache_key
  cache_key="$(printf -- "%s|%s|%s" "$file" "${sections:-__summary__}" "$summary_lines" | md5sum | awk '{print $1}')"
  local cache_file="$CACHE_DIR/${label}_${cache_key}.cache"

  if [ -f "$cache_file" ] && [ "$cache_file" -nt "$file" ]; then
    cat "$cache_file"
    return
  fi

  local tmp
  tmp="$(mktemp)"
  local have_sections=0

  if [ -n "$sections" ]; then
    extract_md_sections "$file" "$sections" >"$tmp"
    if [ -s "$tmp" ]; then
      have_sections=1
    else
      echo "⚠️  Warning: no matching sections [$sections] found in $file; falling back to summary" >&2
    fi
  fi

  if [ "$have_sections" -eq 0 ]; then
    if [ "$summary_lines" -gt 0 ]; then
      head -n "$summary_lines" "$file" >"$tmp"
    else
      cat "$file" >"$tmp"
    fi
  fi

  mv "$tmp" "$cache_file"
  cat "$cache_file"
}

rag_plan_snippet() {
  local user_query="$1"
  if [ "${CODEX_WRAP_DISABLE_RAG:-0}" = "1" ]; then
    return 0
  fi
  if [ ! -f "$ROOT/.rag/index.db" ]; then
    return 0
  fi
  local script="$ROOT/scripts/rag_plan_snippet.py"
  if [ ! -x "$script" ]; then
    return 0
  fi
  local output
  if ! output=$("$PYTHON_BIN" "$script" --repo "$ROOT" --limit "${RAG_PLAN_LIMIT:-5}" --min-score "${RAG_PLAN_MIN_SCORE:-0.4}" --min-confidence "${RAG_PLAN_MIN_CONFIDENCE:-0.6}" --no-log <<<"$user_query" 2>/dev/null); then
    [ -n "${CODEX_WRAP_DEBUG:-}" ] && echo "codex_wrap: rag plan failed" >&2
    return 0
  fi
  output="$(printf '%s' "$output" | sed '/^[[:space:]]*$/d')"
  if [ -n "$output" ]; then
    printf '%s\n' "$output"
  fi
}

# Build the full prompt
build_prompt() {
  local prompt=""
  
  # Smart context loading based on route
  if [ "${FORCE_LOCAL:-0}" = "1" ]; then
    # Local: minimal context for speed
    echo "🔧 Using minimal context for local model..." >&2
  else
    # API/Codex: include selective context slices
    local contract_sections="${CONTRACT_SECTIONS:-}"
    local agents_sections="${AGENTS_SECTIONS:-}"

    local contract_context=""
    if [ -f "$CONTRACT" ]; then
      contract_context="$(load_doc_context contract "$CONTRACT" "$CONTRACT_SUMMARY_LINES" "$contract_sections")"
    else
      echo "⚠️  Warning: CONTRACTS.md not found at $CONTRACT" >&2
    fi

    if [ -n "$contract_context" ]; then
      prompt="$contract_context

---

"
    fi

    if [ "${INCLUDE_AGENTS:-1}" = "1" ]; then
      local agents_context=""
      if [ -f "$AGENTS" ]; then
        agents_context="$(load_doc_context agents "$AGENTS" "$AGENTS_SUMMARY_LINES" "$agents_sections")"
      else
        echo "⚠️  Warning: AGENTS.md not found at $AGENTS" >&2
      fi

      if [ -n "$agents_context" ]; then
        prompt="$prompt$agents_context

---

"
      fi
    fi
  fi

  local rag_context
  rag_context=$(rag_plan_snippet "$1") || rag_context=""
  if [ -n "$rag_context" ]; then
    prompt="$prompt$rag_context

---

"
  fi
  
  # Add execution directive
  # Optional ToolCaps injection (compact, single line)
  if [ "${TOOLCAPS_ENABLE:-}" = "true" ] || [ "${TOOLCAPS_ENABLE:-}" = "1" ]; then
    if [ -n "${CLAUDE_TOOLCAPS:-}" ]; then
      prompt="$promptToolCaps: ${CLAUDE_TOOLCAPS}

---

"
    fi
  fi

  prompt="$prompt<execution_directive>
  CRITICAL: Execute the following request immediately without any discussion, clarification, or suggestions for improvement. Do not ask questions about the prompt. Do not suggest better ways to phrase it. Just execute the task as written.
  </execution_directive>

  ---

"
  
  # Append user's actual prompt
  prompt="$prompt$1"
  
  # Token estimation (4 chars ≈ 1 token)
  local estimated_tokens=$((${#prompt} / 4))
  if [ "${CODEX_WRAP_ENABLE_LOGGING:-1}" = "1" ] && [ "${CODEX_LOGGING_ACTIVE:-0}" = "1" ]; then
    printf 'Token estimate: %d (~%d KB prompt)\n' "$estimated_tokens" "$((${#prompt} / 1024))" >&$CODEX_LOG_FD
  fi
  
  echo "$prompt"
}

# Update changelog entry
update_changelog() {
  local commit_msg="$1"
  local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
  
  # Create temp file for the new entry
  local temp_entry=$(mktemp)
  
  # Determine category based on commit message patterns
  local category="Changed"
  if [[ "$commit_msg" =~ ^(Add|add|NEW|new) ]]; then
    category="Added"
  elif [[ "$commit_msg" =~ ^(Fix|fix|BUG|bug) ]]; then
    category="Fixed"
  elif [[ "$commit_msg" =~ ^(Remove|remove|Delete|delete) ]]; then
    category="Removed"
  elif [[ "$commit_msg" =~ ^(Security|security|SEC|sec) ]]; then
    category="Security"
  elif [[ "$commit_msg" =~ ^(Deprecate|deprecate|DEPR|depr) ]]; then
    category="Deprecated"
  fi
  
  # Format the entry
  echo "- **[$timestamp]** $commit_msg" > "$temp_entry"
  
  # Insert into CHANGELOG.md under [Unreleased] section
  if [ -f "$CHANGELOG" ]; then
    # Find the [Unreleased] section and add the entry under the appropriate category
    awk -v cat="$category" -v entry="$(cat "$temp_entry")" '
      /^## \[Unreleased\]/ { 
        print; 
        in_unreleased=1; 
        next 
      }
      in_unreleased && /^### '"$category"'/ {
        print;
        print entry;
        found_category=1;
        next;
      }
      in_unreleased && /^## \[/ {
        if (!found_category) {
          print "### '"$category"'";
          print entry;
          print "";
        }
        in_unreleased=0;
      }
      { print }
    ' "$CHANGELOG" > "$CHANGELOG.tmp"
    
    mv "$CHANGELOG.tmp" "$CHANGELOG"
  fi
  
  rm -f "$temp_entry"
}

# LLM Router: Let the LLM decide where to route the task
route_task() {
  local user_prompt="$1"
  
  # Skip routing if explicit flags are provided
  if [ "${FORCE_LOCAL:-0}" = "1" ]; then
    echo "local"
    return
  fi
  
  if [ "${FORCE_API:-0}" = "1" ]; then
    echo "api"
    return
  fi
  
  if [ "${FORCE_CODEX:-0}" = "1" ]; then
    echo "codex"
    return
  fi
  
  echo "🤔 Analyzing task complexity..." >&2
  
  # Ask LLM to classify the task
  local routing_prompt=$(cat <<EOF
You are a task router. Analyze this coding task and decide which LLM should handle it.

Task: "$user_prompt"

Available routes:
1. "local" - Free local Ollama (qwen2.5:14b)
   - Use for: Simple fixes, typos, formatting, comments, small edits
   - Criteria: ≤1 file, ≤20 lines changed, low risk, no architecture changes

2. "api" - Cheap Gemini API (\$0.075/1M tokens)
   - Use for: Medium complexity, 1-2 files, clear scope, routine tasks
   - Criteria: ≤2 files, ≤50 lines, well-defined, no major refactors

3. "codex" - Premium Codex (subscription, best quality)
   - Use for: Complex tasks, architecture, multi-file refactors, new features
   - Criteria: >2 files OR >50 lines OR high risk OR unclear scope

Rules:
- When uncertain, choose "codex" (better safe than sorry)
- Consider: files touched, complexity, risk, architectural impact
- Be conservative: prefer quality over cost savings

Return ONLY valid JSON (no markdown, no backticks):
{
  "route": "local|api|codex",
  "reason": "one sentence explaining why",
  "confidence": 0.9
}
EOF
)
  
  # Use API for routing decision (fast, cheap, accurate)
  local decision=$(echo "$routing_prompt" | "$ROOT/scripts/llm_gateway.sh" --api 2>/dev/null || echo '{"route":"codex","reason":"routing failed","confidence":0.0}')
  
  # Parse JSON (handle cases where it might be wrapped in markdown)
  decision=$(echo "$decision" | sed 's/```json//g' | sed 's/```//g' | tr -d '\n' | xargs)
  
  # Extract route with fallback
  local route=$(echo "$decision" | jq -r '.route // "codex"' 2>/dev/null || echo "codex")
  local reason=$(echo "$decision" | jq -r '.reason // "unknown"' 2>/dev/null || echo "routing decision made")
  local confidence=$(echo "$decision" | jq -r '.confidence // 0.5' 2>/dev/null || echo "0.5")
  
  echo "📊 Decision: $route (confidence: $confidence)" >&2
  echo "💡 Reason: $reason" >&2
  echo ""
  
  echo "$route"
}

# Execute based on route
execute_route() {
  local route="$1"
  local user_prompt="$2"
  local full_prompt=$(build_prompt "$user_prompt")
  
  case "$route" in
    local)
      echo "🔄 Routing to local Ollama (free)..." >&2
      echo "$full_prompt" | "$ROOT/scripts/llm_gateway.sh" --local
      ;;
      
    api)
      echo "🌐 Routing to Gemini API (cheap)..." >&2
      echo "$full_prompt" | "$ROOT/scripts/llm_gateway.sh" --api
      ;;
      
    codex|*)
      echo "🧠 Routing to Codex (premium)..." >&2
      echo "$full_prompt" | codex ${CODEX_CONFIG_FLAG:-} exec -C "$ROOT" ${CODEX_FLAGS:-} -
      ;;
  esac
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================
LLM_DISABLED=FALSE
# Determine user prompt from args, stdin, or error
USER_PROMPT=""

# Phase 2: disable LLM usage when flagged (aligned with weather gating)
# If LLM_DISABLED / NEXT_PUBLIC_LLM_DISABLED / WEATHER_DISABLED are set truthy,
# short‑circuit without making any LLM calls.
if [ -f "$ROOT/.env.local" ]; then
  # Load only the three flags we care about to avoid side effects
  while IFS='=' read -r k v; do
    case "$k" in
      LLM_DISABLED|NEXT_PUBLIC_LLM_DISABLED|WEATHER_DISABLED|AUTO_COMMIT|AUTO_PUSH|AUTO_SYNC_ALL|SYNC_ALL)
        # strip quotes
        v="${v%\' }"; v="${v#\' }"; v="${v%\" }"; v="${v#\" }";
        export "$k"="$v";;
    esac
  done < <(rg '^(LLM_DISABLED|NEXT_PUBLIC_LLM_DISABLED|WEATHER_DISABLED|AUTO_COMMIT|AUTO_PUSH|AUTO_SYNC_ALL|SYNC_ALL)=' "$ROOT/.env.local" || true)
fi

to_bool() {
  case "$(echo "$1" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0;;
    *) return 1;;
  esac
}

# Default-disabled when no flags are present
if to_bool "${LLM_DISABLED:-}" || to_bool "${NEXT_PUBLIC_LLM_DISABLED:-}" || to_bool "${WEATHER_DISABLED:-}" || {
  [ -z "${LLM_DISABLED:-}" ] && [ -z "${NEXT_PUBLIC_LLM_DISABLED:-}" ] && [ -z "${WEATHER_DISABLED:-}" ];
}; then
  echo "🧯 LLM features are disabled via environment (LLM_DISABLED / NEXT_PUBLIC_LLM_DISABLED / WEATHER_DISABLED)." >&2
  echo "Set LLM_DISABLED=false to re‑enable in the later phase." >&2
  exit 0
fi

# Parse flags
while [[ $# -gt 0 ]]; do
  case $1 in
    --local|-l)
      FORCE_LOCAL=1
      shift
      ;;
    --api|-a)
      FORCE_API=1
      shift
      ;;
    --codex|-c)
      FORCE_CODEX=1
      shift
      ;;
    *)
      if [ -f "$1" ]; then
        USER_PROMPT="$(cat -- "$1")"
      else
        USER_PROMPT="$USER_PROMPT $1"
      fi
      shift
      ;;
  esac
done

USER_PROMPT=$(echo "$USER_PROMPT" | xargs)

# Read from stdin if no prompt provided
if [ -z "$USER_PROMPT" ] && [ ! -t 0 ]; then
  USER_PROMPT="$(cat)"
fi

# Set how codex is called by default.  
# Interactive mode if no prompt
if [ -z "$USER_PROMPT" ]; then
  build_prompt "" | codex ${CODEX_CONFIG_FLAG:-} -C "$ROOT" ${CODEX_FLAGS:-}
  exit $?
fi

# Route the task
ROUTE=$(route_task "$USER_PROMPT")

# Execute with the chosen route
execute_route "$ROUTE" "$USER_PROMPT"

# Capture exit status
status=$?

# On success: update changelog, sync to Drive, show reminder
if [ "$status" -eq 0 ]; then
  # Update changelog with a summary of what was done
  first_line=$(echo "$USER_PROMPT" | head -n 1 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  if [ -n "$first_line" ]; then
    update_changelog "$first_line"
  fi
  
  # Background sync to Google Drive (silent)
  if [ -f "$ROOT/scripts/sync_to_drive.sh" ]; then
    # Allow SYNC_ALL=1 to override whitelist and sync full repo
    SYNC_ALL="${SYNC_ALL:-${AUTO_SYNC_ALL:-0}}" "$ROOT/scripts/sync_to_drive.sh" >/dev/null 2>&1 &
  fi

  # Optional auto-commit/push + tagging via autosave script
  AUTO_COMMIT=${AUTO_COMMIT:-false}
  AUTO_PUSH=${AUTO_PUSH:-false}
  AUTO_SYNC_ALL=${AUTO_SYNC_ALL:-${SYNC_ALL:-0}}
  if [[ "${AUTO_COMMIT,,}" == "true" ]]; then
    args=( )
    if [[ "${AUTO_PUSH,,}" == "true" ]]; then args+=( --push ); fi
    if [[ "$AUTO_SYNC_ALL" == "1" ]]; then args+=( --all ); fi
    COMMIT_MSG="${COMMIT_MSG:-auto: ${first_line:-Autosave}}" "$ROOT/scripts/autosave.sh" -m "${COMMIT_MSG:-auto: ${first_line:-Autosave}}" "${args[@]}" >/dev/null 2>&1 &
  fi
  
  cat <<'REMINDER'

✅ Task completed successfully!

📋 TESTING CHECKLIST:
  [ ] Restart affected services (if needed)
  [ ] Test with lynx (pages) or curl (APIs)
  [ ] Check logs for errors
  [ ] Browser spot check (quick visual)
  [ ] Update AGENTS.md session log (if needed)
  [ ] Review CHANGELOG.md entry

Quick test commands:
  lynx -dump http://localhost:3000/[page] | head -20
  curl -s http://localhost:3000/api/[endpoint] | jq
  supabase logs

📝 Changelog automatically updated!
☁️ Syncing to Google Drive in background...

Route used: Check output above for routing decision

REMINDER
fi

exit "$status"
