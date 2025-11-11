#!/usr/bin/env bash
# gemini_wrap.sh - Smart LLM routing with self-classification
set -euo pipefail

if [ "${LLMC_CONCURRENCY:-off}" = "on" ] && [ -n "${CHANGESET_PATH:-}" ] && [ -f "${CHANGESET_PATH}" ]; then
  echo "[llmc] integrating ${CHANGESET_PATH}" >&2
  if [ "${LLMC_SHADOW_MODE:-off}" = "on" ]; then
    scripts/llmc_edit.sh --changeset "${CHANGESET_PATH}" || exit $?
  else
    scripts/llmc_edit.sh --changeset "${CHANGESET_PATH}" || exit $?
  fi
fi

# Resolve execution and target roots
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXEC_ROOT="${LLMC_EXEC_ROOT:-$SCRIPT_ROOT}"
REPO_ROOT="${LLMC_TARGET_REPO:-$EXEC_ROOT}"

# Pre-scan args for --repo to allow overriding before path-dependent setup
ORIGINAL_ARGS=("$@")
for ((i=0; i<${#ORIGINAL_ARGS[@]}; i++)); do
  case "${ORIGINAL_ARGS[i]}" in
    --repo)
      if (( i + 1 < ${#ORIGINAL_ARGS[@]} )); then
        REPO_ROOT="$(realpath "${ORIGINAL_ARGS[i+1]}")"
      fi
      ;;
    --repo=*)
      REPO_ROOT="$(realpath "${ORIGINAL_ARGS[i]#*=}")"
      ;;
  esac
done

CONTRACT="$REPO_ROOT/CONTRACTS.md"
AGENTS="$REPO_ROOT/AGENTS.md"
CHANGELOG="$REPO_ROOT/CHANGELOG.md"
PYTHON_BIN="${PYTHON_BIN:-python3}"

GEMINI_LOG_FILE="${GEMINI_LOG_FILE:-$REPO_ROOT/logs/geminilog.txt}"
mkdir -p "$(dirname "$GEMINI_LOG_FILE")"
touch "$GEMINI_LOG_FILE"
if [ "${GEMINI_WRAP_ENABLE_LOGGING:-1}" = "1" ]; then
  FORCE_LOG="${GEMINI_WRAP_FORCE_LOGGING:-0}"
  # Preserve real TTY for interactive gemini sessions; only tee when stdout/stderr are not TTYs or explicitly forced.
  if { [ -t 1 ] && [ -t 2 ]; } && [ "$FORCE_LOG" != "1" ]; then
    : # Skip tee logging to avoid breaking gemini which requires a TTY.
  else
    exec > >(tee -a "$GEMINI_LOG_FILE")
    exec 2> >(tee -a "$GEMINI_LOG_FILE" >&2)
  fi
fi

GEMINI_LOGGING_ACTIVE=0
if [ "${GEMINI_WRAP_ENABLE_LOGGING:-1}" = "1" ]; then
  # Open a dedicated FD for structured trace logging without disturbing TTY output.
  exec {GEMINI_LOG_FD}>>"$GEMINI_LOG_FILE"
  {
    printf -- '\n--- gemini_wrap start %s pid=%d ---\n' "$(date -Is)" "$$"
  } >&$GEMINI_LOG_FD
  GEMINI_LOGGING_ACTIVE=1

  BASH_XTRACEFD=$GEMINI_LOG_FD
  PS4='+ [gemini_wrap] '
  set -o xtrace
fi

gemini_wrap_on_exit() {
  local rc=$?
  if [ "${GEMINI_LOGGING_ACTIVE:-0}" = "1" ]; then
    set +o xtrace
    printf -- '--- gemini_wrap end %s pid=%d exit=%d ---\n' "$(date -Is)" "$$" "$rc" >&$GEMINI_LOG_FD
  fi
  return "$rc"
}
trap gemini_wrap_on_exit EXIT

# Short usage/flag reference for standard -h/--help behavior
print_gemini_wrap_help() {
  cat <<'EOF'
Usage: scripts/gemini_wrap.sh [options] [prompt|prompt_file]

Options:
  -l, --local          Force routing to the local Ollama profile
  -a, --api            Force routing to the remote API profile (e.g., a cheaper Gemini model)
  -g, --gemini         Force routing directly to the premium Gemini model
      --repo PATH      Run against a different repository root
  -h, --help           Show this help message and exit

Examples:
  scripts/gemini_wrap.sh --local "Fix the failing unit test"
  scripts/gemini_wrap.sh --repo ../other/repo task.txt
EOF
}

# Resolve Gemini approval policy from env or repo-local config
REPO_GEMINI_TOML="$REPO_ROOT/.gemini/config.toml"

resolve_approval_policy() {
  # Env overrides take precedence
  if [ -n "${GEMINI_APPROVAL:-}" ]; then echo "$GEMINI_APPROVAL"; return; fi
  if [ -n "${APPROVAL_POLICY:-}" ]; then echo "$APPROVAL_POLICY"; return; fi

  # Fallback to repo .gemini/config.toml if present
  if [ -f "$REPO_GEMINI_TOML" ]; then
    local val
    val=$(sed -nE 's/^[[:space:]]*ask_for_approval[[:space:]]*=[[:space:]]*"?([A-Za-z-]+)"?.*/\1/p' "$REPO_GEMINI_TOML" | tail -n 1)
    case "$val" in
      untrusted|on-failure|on-request|never) echo "$val"; return ;;
    esac
  fi
  echo ""
}

# Only set if not already provided by caller
if [ -z "${GEMINI_CONFIG_FLAG:-}" ]; then
  _ap="$(resolve_approval_policy)"
  if [ -n "$_ap" ]; then
    GEMINI_CONFIG_FLAG="-a $_ap"
    [ -n "${GEMINI_WRAP_DEBUG:-}" ] && echo "gemini_wrap: approval policy -> $_ap" >&2
  else
    [ -n "${GEMINI_WRAP_DEBUG:-}" ] && echo "gemini_wrap: approval policy not set" >&2
  fi
fi

# Cache directory for reused context slices
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/gemini_wrap"
if ! mkdir -p "$CACHE_DIR" 2>/dev/null; then
  CACHE_DIR="$REPO_ROOT/.cache/gemini_wrap"
  mkdir -p "$CACHE_DIR"
fi

CACHE_LOOKUP_RESULT=""
CACHE_LOOKUP_STATUS="disabled"
CACHE_LOOKUP_SCORE=""

CACHE_LOOKUP_RESULT=""

DEEP_RESEARCH_RECOMMENDED=0
DEEP_RESEARCH_RESULT_JSON=""
DEEP_RESEARCH_REMINDER=""
DEEP_RESEARCH_ROUTE_OVERRIDE=0

# Load ToolCaps state if present (written by scripts/tool_health.sh)
TOOLS_STATE_ENV="$REPO_ROOT/.gemini/state/tools.env"
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

deep_research_check() {
  local prompt="$1"
  if [ "${GEMINI_WRAP_DISABLE_DEEP_RESEARCH:-0}" = "1" ]; then
    DEEP_RESEARCH_RECOMMENDED=0
    DEEP_RESEARCH_RESULT_JSON=""
    DEEP_RESEARCH_REMINDER=""
    return 0
  fi
  if [ -z "$prompt" ]; then
    DEEP_RESEARCH_RECOMMENDED=0
    DEEP_RESEARCH_RESULT_JSON=""
    DEEP_RESEARCH_REMINDER=""
    return 0
  fi

  local tmp
  tmp="$(mktemp)"
  printf '%s' "$prompt" >"$tmp"
  local detection
  if ! detection=$("$PYTHON_BIN" -m tools.deep_research.detector --prompt-file "$tmp" 2>/dev/null); then
    rm -f "$tmp"
    return 0
  fi
  rm -f "$tmp"

  DEEP_RESEARCH_RESULT_JSON="$detection"
  local needs
  needs="$(echo "$detection" | jq -r '.needs_deep_research // false' 2>/dev/null || echo "false")"
  if [ "$needs" != "true" ]; then
    DEEP_RESEARCH_RECOMMENDED=0
    DEEP_RESEARCH_REMINDER=""
    return 0
  fi

  DEEP_RESEARCH_RECOMMENDED=1
  local score confidence
  score="$(echo "$detection" | jq -r '.score // 0' 2>/dev/null || echo "0")"
  confidence="$(echo "$detection" | jq -r '.confidence // 0' 2>/dev/null || echo "0")"

  echo "" >&2
  echo "🚩 Deep research suggested (score ${score}, confidence ${confidence})" >&2

  local reasons
  reasons="$(echo "$detection" | jq -r '.reasons[]?' 2>/dev/null)"
  if [ -n "$reasons" ]; then
    echo "Reasons:" >&2
    echo "$reasons" | sed 's/^/- /' >&2
  fi

  local service_lines
  service_lines="$(echo "$detection" | jq -r '.services[]? | [.name, (.remaining_today // "∞"), (.daily_quota // "∞"), (.used_today // 0), (.url // ""), (.notes // "")] | @tsv' 2>/dev/null)"
  if [ -n "$service_lines" ]; then
    echo "" >&2
    echo "Manual deep research services:" >&2
    while IFS=$'\t' read -r name remaining quota used url notes; do
      [ -z "$name" ] && continue
      local remaining_display="$remaining"
      if [ "$remaining_display" = "∞" ] || [ "$remaining_display" = "null" ]; then
        remaining_display="∞"
      elif [ -z "$remaining_display" ]; then
        remaining_display="n/a"
      fi
      local quota_display="$quota"
      if [ "$quota_display" = "∞" ] || [ "$quota_display" = "null" ] || [ -z "$quota_display" ]; then
        quota_display="unlimited"
      else
        quota_display="${quota_display}/day"
      fi
      local note_display=""
      [ -n "$notes" ] && [ "$notes" != "null" ] && note_display=" (${notes})"
      local url_display=""
      [ -n "$url" ] && [ "$url" != "null" ] && url_display=" — ${url}"
      printf '  • %s — remaining: %s, quota: %s%s%s\n' "$name" "$remaining_display" "$quota_display" "$url_display" "$note_display" >&2
    done <<<"$service_lines"
  fi

  echo "" >&2
  DEEP_RESEARCH_REMINDER=$'Manual deep research recommended.\n- Use the services listed above before high-impact work.\n- Drop notes into research/incoming/ using research/deep_research_notes.template.md, then run ./scripts/deep_research_ingest.sh.'
  return 0
}

rag_plan_snippet() {
  local user_query="$1"
  local helper="$EXEC_ROOT/scripts/rag_plan_helper.sh"
  if [ ! -x "$helper" ]; then
    return 0
  fi
  local output
  if ! output=$(GEMINI_WRAP_DISABLE_RAG="${GEMINI_WRAP_DISABLE_RAG:-0}" PYTHON_BIN="$PYTHON_BIN" "$helper" --repo "$REPO_ROOT" <<<"$user_query" 2>/dev/null); then
    [ -n "${GEMINI_WRAP_DEBUG:-}" ] && echo "gemini_wrap: rag plan helper failed" >&2
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
  if [ "${GEMINI_WRAP_ENABLE_LOGGING:-1}" = "1" ] && [ "${GEMINI_LOGGING_ACTIVE:-0}" = "1" ]; then
    printf 'Token estimate: %d (~%d KB prompt)\n' "$estimated_tokens" "$((${#prompt} / 1024))" >&$GEMINI_LOG_FD
  fi
  
  echo "$prompt"
}

semantic_cache_enabled() {
  if [ "${SEMANTIC_CACHE_DISABLE:-0}" = "1" ]; then
    return 1
  fi
  if [ "${SEMANTIC_CACHE_ENABLE:-1}" = "0" ]; then
    return 1
  fi
  return 0
}

semantic_cache_provider_for_route() {
  local route="$1"
  case "$route" in
    local)
      echo "${OLLAMA_MODEL:-qwen2.5:14b-instruct-q4_K_M}"
      ;;
    api)
      echo "${GEMINI_MODEL:-gemini-2.5-flash}"
      ;;
    gemini-pro)
      echo "gemini-pro"
      ;;
    gemini|*)
      echo "gemini"
      ;;
  esac
}

semantic_cache_lookup() {
  if ! semantic_cache_enabled; then
    CACHE_LOOKUP_STATUS="disabled"
    CACHE_LOOKUP_SCORE=""
    return 1
  fi
  CACHE_LOOKUP_STATUS="miss"
  CACHE_LOOKUP_SCORE=""
  local route="$1"
  local prompt="$2"
  local provider="$3"
  local user_prompt="${USER_PROMPT:-}"
  local prompt_file
  prompt_file=$(mktemp)
  printf '%s' "$prompt" >"$prompt_file"
  local user_prompt_file=""
  if [ -n "$user_prompt" ]; then
    user_prompt_file=$(mktemp)
    printf '%s' "$user_prompt" >"$user_prompt_file"
  fi
  local min_score_arg=()
  if [ -n "${SEMANTIC_CACHE_MIN_SCORE:-}" ]; then
    min_score_arg=(--min-score "${SEMANTIC_CACHE_MIN_SCORE}")
  fi
  local provider_arg=()
  if [ -n "$provider" ]; then
    provider_arg=(--provider "$provider")
  fi
  local result
  local user_prompt_arg=()
  if [ -n "$user_prompt_file" ]; then
    user_prompt_arg=(--user-prompt-file "$user_prompt_file")
  fi
  if ! result=$("$PYTHON_BIN" -m tools.cache.cli lookup --route "$route" "${provider_arg[@]}" "${user_prompt_arg[@]}" "${min_score_arg[@]}" --prompt-file "$prompt_file" 2>/dev/null); then
    rm -f "$prompt_file"
    [ -n "$user_prompt_file" ] && rm -f "$user_prompt_file"
    return 1
  fi
  rm -f "$prompt_file"
  [ -n "$user_prompt_file" ] && rm -f "$user_prompt_file"
  local hit
  hit=$(echo "$result" | jq -r '.hit // false' 2>/dev/null)
  if [ "$hit" = "true" ]; then
    CACHE_LOOKUP_RESULT="$result"
    CACHE_LOOKUP_STATUS="hit"
    CACHE_LOOKUP_SCORE=$(echo "$result" | jq -r '.score // ""' 2>/dev/null)
    return 0
  fi
  CACHE_LOOKUP_RESULT=""
  CACHE_LOOKUP_STATUS="miss"
  CACHE_LOOKUP_SCORE=""
  return 1
}

semantic_cache_store() {
  if ! semantic_cache_enabled; then
    return
  fi
  local route="$1"
  local provider="$2"
  local prompt="$3"
  local response="$4"
  local prompt_file response_file
  prompt_file=$(mktemp)
  response_file=$(mktemp)
  printf '%s' "$prompt" >"$prompt_file"
  printf '%s' "$response" >"$response_file"
  "$PYTHON_BIN" -m tools.cache.cli store \
    --route "$route" \
    --provider "$provider" \
    --user-prompt "$USER_PROMPT" \
    --prompt-file "$prompt_file" \
    --response-file "$response_file" \
    >/dev/null 2>&1 || true
  rm -f "$prompt_file" "$response_file"
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
  
  if [ "${FORCE_GEMINI:-0}" = "1" ]; then
    echo "gemini"
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

3. "gemini" - Premium Gemini model (e.g., Gemini Pro)
   - Use for: Complex tasks, architecture, multi-file refactors, new features
   - Criteria: >2 files OR >50 lines OR high risk OR unclear scope

Rules:
- When uncertain, choose "gemini" (better safe than sorry)
- Consider: files touched, complexity, risk, architectural impact
- Be conservative: prefer quality over cost savings

Return ONLY valid JSON (no markdown, no backticks):
{
  "route": "local|api|gemini",
  "reason": "one sentence explaining why",
  "confidence": 0.9
}
EOF
)
  
  # Use API for routing decision (fast, cheap, accurate)
  local decision=$(echo "$routing_prompt" | "$EXEC_ROOT/scripts/llm_gateway.sh" --api 2>/dev/null || echo '{"route":"gemini","reason":"routing failed","confidence":0.0}')
  
  # Parse JSON (handle cases where it might be wrapped in markdown)
  decision=$(echo "$decision" | sed 's/```json//g' | sed 's/```//g' | tr -d '\n' | xargs)
  
  # Extract route with fallback
  local route=$(echo "$decision" | jq -r '.route // "gemini"' 2>/dev/null || echo "gemini")
  local reason=$(echo "$decision" | jq -r '.reason // "unknown"' 2>/dev/null || echo "routing decision made")
  local confidence=$(echo "$decision" | jq -r '.confidence // 0.5' 2>/dev/null || echo "0.5")
  
  echo "📊 Decision: $route (confidence: $confidence)" >&2
  echo "💡 Reason: $reason" >&2
  echo ""

  if [ "${DEEP_RESEARCH_RECOMMENDED:-0}" = "1" ] && [ "${DEEP_RESEARCH_ALLOW_AUTO:-0}" != "1" ]; then
    if [ "$route" != "local" ]; then
      echo "🔒 Deep research gating: overriding route to 'local' until research notes are ingested. Set DEEP_RESEARCH_ALLOW_AUTO=1 to bypass." >&2
      route="local"
      DEEP_RESEARCH_ROUTE_OVERRIDE=1
    fi
  fi
  
  echo "$route"
}

# Execute based on route
execute_route() {
  local route="$1"
  local user_prompt="$2"
  local full_prompt
  full_prompt=$(build_prompt "$user_prompt")
  local provider
  provider=$(semantic_cache_provider_for_route "$route")

  if semantic_cache_lookup "$route" "$full_prompt" "$provider"; then
    local score="${CACHE_LOOKUP_SCORE:-1}"
    if [ "${SEMANTIC_CACHE_PROBE:-0}" = "1" ]; then
      echo "🔍 Semantic cache hit (score ${score}) [probe]" >&2
      CACHE_LOOKUP_RESULT=""
    else
      echo "⚡ Semantic cache hit (score ${score})" >&2
      echo "$CACHE_LOOKUP_RESULT" | jq -r '.response // ""'
      CACHE_LOOKUP_RESULT=""
      return 0
    fi
  else
    if [ "${SEMANTIC_CACHE_PROBE:-0}" = "1" ]; then
      echo "🔍 Semantic cache miss (probe mode)" >&2
    fi
  fi

  local response=""
  local status=0
  case "$route" in
    local)
      echo "🔄 Routing to local Ollama (free)..." >&2
      response=$(RAG_USER_PROMPT="$user_prompt" "$EXEC_ROOT/scripts/llm_gateway.sh" --local <<<"$full_prompt")
      status=$?
      ;;
      
    api)
      echo "🌐 Routing to Gemini API (cheap)..." >&2
      response=$(RAG_USER_PROMPT="$user_prompt" "$EXEC_ROOT/scripts/llm_gateway.sh" --gemini-api <<<"$full_prompt")
      status=$?
      ;;
      
    gemini|*)
      echo "🚀 Routing to Gemini (premium)..." >&2
      response=$(gemini --yolo "$full_prompt")
      status=$?
      ;;
  esac
  # Post-process for LLM-declared tool calls (search_tools/describe_tool)
  local processed_response="$response"
  if [ -x "$EXEC_ROOT/scripts/tool_dispatch.sh" ]; then
    processed_response="$(printf '%s' "$response" | "$EXEC_ROOT/scripts/tool_dispatch.sh" 2>/dev/null || printf '%s' "$response")"
  fi

  printf '%s' "$processed_response"
  case "$processed_response" in
    *$'\n') ;;
    *) echo ;;
  esac
  if [ $status -eq 0 ]; then
    semantic_cache_store "$route" "$provider" "$full_prompt" "$processed_response"
  fi
  CACHE_LOOKUP_RESULT=""
  return $status
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
if [ -f "$REPO_ROOT/.env.local" ]; then
  # Load only the three flags we care about to avoid side effects
  while IFS='=' read -r k v; do
    case "$k" in
      LLM_DISABLED|NEXT_PUBLIC_LLM_DISABLED|WEATHER_DISABLED|AUTO_COMMIT|AUTO_PUSH|AUTO_SYNC_ALL|SYNC_ALL)
        # strip quotes
        v="${v%\' }"; v="${v#\' }"; v="${v%\" }"; v="${v#\" }";
        export "$k"="$v";;
    esac
  done < <(rg '^(LLM_DISABLED|NEXT_PUBLIC_LLM_DISABLED|WEATHER_DISABLED|AUTO_COMMIT|AUTO_PUSH|AUTO_SYNC_ALL|SYNC_ALL)=' "$REPO_ROOT/.env.local" || true)
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
    --gemini|-g)
      FORCE_GEMINI=1
      shift
      ;;
    --repo)
      shift
      if [ $# -gt 0 ]; then
        REPO_ROOT="$(realpath "$1")"
        export LLMC_TARGET_REPO="$REPO_ROOT"
        CONTRACT="$REPO_ROOT/CONTRACTS.md"
        AGENTS="$REPO_ROOT/AGENTS.md"
        CHANGELOG="$REPO_ROOT/CHANGELOG.md"
        GEMINI_LOG_FILE="${GEMINI_LOG_FILE:-$REPO_ROOT/logs/geminilog.txt}"
      fi
      shift || true
      ;;
    --repo=*)
      REPO_ROOT="$(realpath "${1#*=}")"
      export LLMC_TARGET_REPO="$REPO_ROOT"
      CONTRACT="$REPO_ROOT/CONTRACTS.md"
      AGENTS="$REPO_ROOT/AGENTS.md"
      CHANGELOG="$REPO_ROOT/CHANGELOG.md"
      GEMINI_LOG_FILE="${GEMINI_LOG_FILE:-$REPO_ROOT/logs/geminilog.txt}"
      shift
      ;;
    --help|-h)
      print_gemini_wrap_help
      exit 0
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

# Set how gemini is called by default.  
# Interactive mode if no prompt
if [ -z "$USER_PROMPT" ]; then
  build_prompt "" | gemini ${GEMINI_CONFIG_FLAG:-}
  exit $?
fi

deep_research_check "$USER_PROMPT"

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
  if [ -f "$EXEC_ROOT/scripts/sync_to_drive.sh" ]; then
    # Allow SYNC_ALL=1 to override whitelist and sync full repo
    SYNC_ALL="${SYNC_ALL:-${AUTO_SYNC_ALL:-0}}" "$EXEC_ROOT/scripts/sync_to_drive.sh" >/dev/null 2>&1 &
  fi

  # Optional auto-commit/push + tagging via autosave script
  AUTO_COMMIT=${AUTO_COMMIT:-false}
  AUTO_PUSH=${AUTO_PUSH:-false}
  AUTO_SYNC_ALL=${AUTO_SYNC_ALL:-${SYNC_ALL:-0}}
  if [[ "${AUTO_COMMIT,,}" == "true" ]]; then
    args=( )
    if [[ "${AUTO_PUSH,,}" == "true" ]]; then args+=( --push ); fi
    if [[ "$AUTO_SYNC_ALL" == "1" ]]; then args+=( --all ); fi
    COMMIT_MSG="${COMMIT_MSG:-auto: ${first_line:-Autosave}}" "$EXEC_ROOT/scripts/autosave.sh" -m "${COMMIT_MSG:-auto: ${first_line:-Autosave}}" "${args[@]}" >/dev/null 2>&1 &
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

  if [ "${DEEP_RESEARCH_RECOMMENDED:-0}" = "1" ]; then
    echo ""
    echo "🧠 Deep research reminder:"
    printf '%s\n' "$DEEP_RESEARCH_REMINDER"
    if [ "${DEEP_RESEARCH_ROUTE_OVERRIDE:-0}" = "1" ]; then
      echo "- Auto-routing stayed on the local tier until manual research notes are captured. Re-run with DEEP_RESEARCH_ALLOW_AUTO=1 after ingestion if you still need premium routing."
    fi
  fi
fi

exit "$status"
