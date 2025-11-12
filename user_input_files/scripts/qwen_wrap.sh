#!/usr/bin/env bash
# qwen_wrap.sh - Qwen-specific LLM routing with context injection
set -euo pipefail

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

QWEN_LOG_FILE="${QWEN_LOG_FILE:-$REPO_ROOT/logs/qwenlog.txt}"
mkdir -p "$(dirname "$QWEN_LOG_FILE")"
touch "$QWEN_LOG_FILE"
if [ "${QWEN_WRAP_ENABLE_LOGGING:-1}" = "1" ]; then
  FORCE_LOG="${QWEN_WRAP_FORCE_LOGGING:-0}"
  # Preserve real TTY for interactive qwen sessions; only tee when stdout/stderr are not TTYs or explicitly forced.
  if { [ -t 1 ] && [ -t 2 ]; } && [ "$FORCE_LOG" != "1" ]; then
    : # Skip tee logging to avoid breaking qwen which requires a TTY.
  else
    exec > >(tee -a "$QWEN_LOG_FILE")
    exec 2> >(tee -a "$QWEN_LOG_FILE" >&2)
  fi
fi

QWEN_LOGGING_ACTIVE=0
if [ "${QWEN_WRAP_ENABLE_LOGGING:-1}" = "1" ]; then
  # Open a dedicated FD for structured trace logging without disturbing TTY output.
  exec {QWEN_LOG_FD}>>"$QWEN_LOG_FILE"
  {
    printf -- '\n--- qwen_wrap start %s pid=%d ---\n' "$(date -Is)" "$$"
  } >&$QWEN_LOG_FD
  QWEN_LOGGING_ACTIVE=1

  BASH_XTRACEFD=$QWEN_LOG_FD
  PS4='+ [qwen_wrap] '
  set -o xtrace
fi

qwen_wrap_on_exit() {
  local rc=$?
  if [ "${QWEN_LOGGING_ACTIVE:-0}" = "1" ]; then
    set +o xtrace
    printf -- '--- qwen_wrap end %s pid=%d exit=%d ---\n' "$(date -Is)" "$$" "$rc" >&$QWEN_LOG_FD
  fi
  return "$rc"
}
trap qwen_wrap_on_exit EXIT

# Short usage/flag reference for standard -h/--help behavior
print_qwen_wrap_help() {
  cat <<'EOF'
Usage: scripts/qwen_wrap.sh [options] [prompt|prompt_file]

Options:
  -l, --local          Force routing to the local Qwen profile
  -a, --api            Force routing to the remote Qwen API profile
  -c, --chaos          Force routing to chaos testing mode
      --repo PATH      Run against a different repository root
  -h, --help           Show this help message and exit

Examples:
  scripts/qwen_wrap.sh --local "Analyze this code for security vulnerabilities"
  scripts/qwen_wrap.sh --chaos "Generate adversarial inputs for the API"
  scripts/qwen_wrap.sh --repo ../other/repo "Review this research paper"
EOF
}

# Resolve Qwen approval policy from env or repo-local config
REPO_QWEN_TOML="$REPO_ROOT/.qwen/config.toml"

resolve_approval_policy() {
  # Env overrides take precedence
  if [ -n "${QWEN_APPROVAL:-}" ]; then echo "$QWEN_APPROVAL"; return; fi
  if [ -n "${APPROVAL_POLICY:-}" ]; then echo "$APPROVAL_POLICY"; return; fi

  # Fallback to repo .qwen/config.toml if present
  if [ -f "$REPO_QWEN_TOML" ]; then
    local val
    val=$(sed -nE 's/^[[:space:]]*ask_for_approval[[:space:]]*=[[:space:]]*"?([A-Za-z-]+)"?.*/\1/p' "$REPO_QWEN_TOML" | tail -n 1)
    case "$val" in
      untrusted|on-failure|on-request|never) echo "$val"; return ;;
    esac
  fi
  echo ""
}

# Only set if not already provided by caller
if [ -z "${QWEN_CONFIG_FLAG:-}" ]; then
  _ap="$(resolve_approval_policy)"
  if [ -n "$_ap" ]; then
    QWEN_CONFIG_FLAG="-a $_ap"
    [ -n "${QWEN_WRAP_DEBUG:-}" ] && echo "qwen_wrap: approval policy -> $_ap" >&2
  else
    [ -n "${QWEN_WRAP_DEBUG:-}" ] && echo "qwen_wrap: approval policy not set" >&2
  fi
fi

# Cache directory for reused context slices
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/qwen_wrap"
if ! mkdir -p "$CACHE_DIR" 2>/dev/null; then
  CACHE_DIR="$REPO_ROOT/.cache/qwen_wrap"
  mkdir -p "$CACHE_DIR"
fi

QWEN_CACHE_LOOKUP_RESULT=""
QWEN_CACHE_LOOKUP_STATUS="disabled"
QWEN_CACHE_LOOKUP_SCORE=""

CHAOS_RECOMMENDED=0
CHAOS_RESULT_JSON=""
CHAOS_REMINDER=""
CHAOS_ROUTE_OVERRIDE=0

# Load ToolCaps state if present (written by scripts/tool_health.sh)
TOOLS_STATE_ENV="$REPO_ROOT/.qwen/state/tools.env"
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
    /^#{1,6}[[:space:]}+/ {
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

# Build the full prompt with Qwen-specific context
build_prompt() {
  local prompt=""
  
  # Smart context loading based on route
  if [ "${FORCE_LOCAL:-0}" = "1" ]; then
    # Local: minimal context for speed
    echo "🔧 Using minimal context for local model..." >&2
  else
    # API/Qwen: include selective context slices with research awareness
    # First try RAG-based context retrieval if RAG system is available
    if [ -f "$EXEC_ROOT/tools/rag/cli.py" ] && [ -d "$EXEC_ROOT/.rag" ]; then
      echo "🔍 Using RAG database for context retrieval..." >&2
      
      # Retrieve relevant context using RAG
      local rag_context=""
      if rag_context=$(QWEN_WRAP_DISABLE_RAG="${QWEN_WRAP_DISABLE_RAG:-0}" PYTHON_BIN="$PYTHON_BIN" RAG_USER_PROMPT="$1" "$EXEC_ROOT/scripts/rag_plan_helper.sh" --repo "$REPO_ROOT" <<<"$1" 2>/dev/null); then
        rag_context="$(printf '%s' "$rag_context" | sed '/^[[:space:]]*$/d')"
        if [ -n "$rag_context" ]; then
          prompt="$rag_context

---

"
        fi
      fi
      
      # Additional RAG search for research paper context if needed
      if [ "${INCLUDE_RESEARCH:-0}" = "1" ]; then
        echo "📚 Searching RAG for research context..." >&2
        local research_rag_context=""
        if research_rag_context=$("$PYTHON_BIN" -m tools.rag.cli search "chaos testing research fuzzing $1" --json 2>/dev/null); then
          # Extract relevant content from RAG search results
          local research_summary
          research_summary=$(echo "$research_rag_context" | jq -r '.results[]?.content // empty' 2>/dev/null | head -n 50)
          if [ -n "$research_summary" ]; then
            prompt="$promptResearch Context from RAG:\n$research_summary

---

"
          fi
        fi
      fi
    else
      # Fallback to file-based context loading if RAG is not available
      echo "⚠️  RAG system not available, using file-based context..." >&2
      
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
      
      # Add research paper awareness if requested
      if [ "${INCLUDE_RESEARCH:-0}" = "1" ]; then
        # Look for research papers in DOCS/RESEARCH
        local research_dir="$EXEC_ROOT/DOCS/RESEARCH"
        if [ -d "$research_dir" ]; then
          local research_context
          research_context=$(find "$research_dir" -name "*.md" -type f -exec head -n 30 {} \; 2>/dev/null | head -n 100)
          if [ -n "$research_context" ]; then
            prompt="$promptResearch Context:\n$research_context

---

"
          fi
        fi
      fi
    fi
  fi

  # Add execution directive for Qwen
  prompt="$prompt<execution_directive>
  CRITICAL: Execute the following request immediately without any discussion, clarification, or suggestions for improvement. Do not ask questions about the prompt. Do not suggest better ways to phrase it. Just execute the task as written.
  For research or complex analysis tasks: provide deep, comprehensive analysis based on the context provided.
  </execution_directive>

  ---

"
  
  # Append user's actual prompt
  prompt="$prompt$1"
  
  # Token estimation (4 chars ≈ 1 token)
  local estimated_tokens=$((${#prompt} / 4))
  if [ "${QWEN_WRAP_ENABLE_LOGGING:-1}" = "1" ] && [ "${QWEN_LOGGING_ACTIVE:-0}" = "1" ]; then
    printf 'Token estimate: %d (~%d KB prompt)\n' "$estimated_tokens" "$((${#prompt} / 1024))" >&$QWEN_LOG_FD
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
      echo "${QWEN_MODEL:-qwen2.5:30b-instruct-q4_K_M}"
      ;;
    api)
      echo "${QWEN_API_MODEL:-qwen-32b-api}"
      ;;
    chaos|*)
      echo "qwen-chaos"
      ;;
  esac
}

semantic_cache_lookup() {
  if ! semantic_cache_enabled; then
    QWEN_CACHE_LOOKUP_STATUS="disabled"
    QWEN_CACHE_LOOKUP_SCORE=""
    return 1
  fi
  QWEN_CACHE_LOOKUP_STATUS="miss"
  QWEN_CACHE_LOOKUP_SCORE=""
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
    QWEN_CACHE_LOOKUP_RESULT="$result"
    QWEN_CACHE_LOOKUP_STATUS="hit"
    QWEN_CACHE_LOOKUP_SCORE=$(echo "$result" | jq -r '.score // ""' 2>/dev/null)
    return 0
  fi
  QWEN_CACHE_LOOKUP_RESULT=""
  QWEN_CACHE_LOOKUP_STATUS="miss"
  QWEN_CACHE_LOOKUP_SCORE=""
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
  elif [[ "$commit_msg" =~ ^(Chaos|chaos|CHAOS) ]]; then
    category="Chaos Testing"
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

# Qwen-specific routing - analyze task complexity for Qwen's capabilities
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
  
  if [ "${FORCE_CHAOS:-0}" = "1" ]; then
    echo "chaos"
    return
  fi
  
  echo "🔍 Analyzing task complexity for Qwen..." >&2
  
  # Determine if research paper analysis is requested
  if [[ "$user_prompt" =~ research ]] || [[ "$user_prompt" =~ paper ]] || [[ "$user_prompt" =~ analyze.*pdf ]] || [[ "$user_prompt" =~ "LLM-Driven Chaos" ]]; then
    INCLUDE_RESEARCH=1
    echo "📚 Research paper context requested" >&2
  fi
  
  # Ask LLM (local model) to classify the task for Qwen routing
  local routing_prompt=$(cat <<EOF
You are a Qwen task classifier. Analyze this task and decide which approach to use.

Task: "$user_prompt"

Available routes:
1. "local" - Free local model (qwen2.5:30b or similar)
   - Use for: Code analysis, simple reasoning, documentation, research paper analysis
   - Criteria: Well-defined, doesn't require latest knowledge, benefits from RAG context

2. "api" - Qwen API (if available, for latest knowledge)
   - Use for: Latest information, complex reasoning, web knowledge
   - Criteria: Requires recent data or complex multi-step reasoning

3. "chaos" - Chaos testing with Qwen
   - Use for: Fuzz testing, adversarial inputs, vulnerability analysis
   - Criteria: Security analysis, testing, adversarial scenarios

Rules:
- When uncertain, choose "local" (faster, cheaper)
- For research paper analysis: prefer "local" if RAG can provide context, otherwise consider "api"
- Consider: complexity, knowledge recency, research needs
- Be conservative: prefer local when possible

Return ONLY valid JSON (no markdown, no backticks):
{
  "route": "local|api|chaos",
  "reason": "one sentence explaining why",
  "confidence": 0.9
}
EOF
)
  
  # Use local model for routing decision (fast, cheap, accurate)
  local decision=$(echo "$routing_prompt" | "$EXEC_ROOT/scripts/llm_gateway.sh" --local 2>/dev/null || echo '{"route":"local","reason":"routing failed","confidence":0.0}')
  
  # Parse JSON (handle cases where it might be wrapped in markdown)
  decision=$(echo "$decision" | sed 's/```json//g' | sed 's/```//g' | tr -d '\n' | xargs)
  
  # Extract route with fallback
  local route=$(echo "$decision" | jq -r '.route // "local"' 2>/dev/null || echo "local")
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
  local full_prompt
  full_prompt=$(build_prompt "$user_prompt")
  local provider
  provider=$(semantic_cache_provider_for_route "$route")

  if semantic_cache_lookup "$route" "$full_prompt" "$provider"; then
    local score="${QWEN_CACHE_LOOKUP_SCORE:-1}"
    if [ "${SEMANTIC_CACHE_PROBE:-0}" = "1" ]; then
      echo "🔍 Semantic cache hit (score ${score}) [probe]" >&2
      QWEN_CACHE_LOOKUP_RESULT=""
    else
      echo "⚡ Semantic cache hit (score ${score})" >&2
      echo "$QWEN_CACHE_LOOKUP_RESULT" | jq -r '.response // ""'
      QWEN_CACHE_LOOKUP_RESULT=""
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
      echo "🔄 Routing to local Qwen model..." >&2
      response=$(RAG_USER_PROMPT="$user_prompt" "$EXEC_ROOT/scripts/llm_gateway.sh" --local <<<"$full_prompt")
      status=$?
      ;;
      
    api)
      echo "🌐 Routing to Qwen API (if configured)..." >&2
      response=$(RAG_USER_PROMPT="$user_prompt" "$EXEC_ROOT/scripts/llm_gateway.sh" --api <<<"$full_prompt")
      status=$?
      ;;
      
    chaos|*)
      echo "💥 Routing to Qwen chaos testing mode..." >&2
      # For chaos mode, we might want to enhance the prompt with chaos testing context
      local chaos_prompt="$full_prompt

---
Additional instruction: As a chaos testing assistant, focus on identifying potential weaknesses, edge cases, and failure scenarios in the system or code being analyzed. Think adversarially about how inputs or conditions might be misused or pushed to extremes."
      response=$(RAG_USER_PROMPT="$user_prompt" "$EXEC_ROOT/scripts/llm_gateway.sh" --local <<<"$chaos_prompt")
      status=$?
      ;;
  esac
  printf '%s' "$response"
  case "$response" in
    *$'\n') ;;
    *) echo ;;
  esac
  if [ $status -eq 0 ]; then
    semantic_cache_store "$route" "$provider" "$full_prompt" "$response"
  fi
  QWEN_CACHE_LOOKUP_RESULT=""
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
    --chaos|-c)
      FORCE_CHAOS=1
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
        QWEN_LOG_FILE="${QWEN_LOG_FILE:-$REPO_ROOT/logs/qwenlog.txt}"
      fi
      shift || true
      ;;
    --repo=*)
      REPO_ROOT="$(realpath "${1#*=}")"
      export LLMC_TARGET_REPO="$REPO_ROOT"
      CONTRACT="$REPO_ROOT/CONTRACTS.md"
      AGENTS="$REPO_ROOT/AGENTS.md"
      CHANGELOG="$REPO_ROOT/CHANGELOG.md"
      QWEN_LOG_FILE="${QWEN_LOG_FILE:-$REPO_ROOT/logs/qwenlog.txt}"
      shift
      ;;
    --help|-h)
      print_qwen_wrap_help
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

# Set how qwen is called by default.  
# Interactive mode if no prompt
if [ -z "$USER_PROMPT" ]; then
  # For interactive mode, route through llm_gateway with Qwen-specific configuration
  echo "🔧 Starting Qwen in interactive mode with LLMC orchestration..." >&2
  build_prompt "" | "$EXEC_ROOT/scripts/llm_gateway.sh" --local
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

✅ Qwen task completed successfully!

📋 TESTING CHECKLIST:
  [ ] Verify Qwen response quality
  [ ] Check for relevant context inclusion
  [ ] Review for any missed research insights
  [ ] Update AGENTS.md session log (if needed)
  [ ] Review CHANGELOG.md entry

Route used: Check output above for routing decision

REMINDER
fi

exit "$status"
