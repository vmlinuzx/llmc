#!/usr/bin/env bash
# claude_wrap.sh - Smart Claude Code routing with context management
# Mirrors codex_wrap.sh but uses Claude Code CLI + supports Azure OpenAI
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

ROOT="$REPO_ROOT"
CONTRACT="$ROOT/CONTRACTS.md"
AGENTS="$ROOT/AGENTS.md"
CHANGELOG="$ROOT/CHANGELOG.md"
PYTHON_BIN="${PYTHON_BIN:-python3}"

CLAUDE_LOG_FILE="${CLAUDE_LOG_FILE:-$ROOT/logs/claudelog.txt}"
mkdir -p "$(dirname "$CLAUDE_LOG_FILE")"
touch "$CLAUDE_LOG_FILE"

# Logging setup
if [ "${CLAUDE_WRAP_ENABLE_LOGGING:-1}" = "1" ]; then
  FORCE_LOG="${CLAUDE_WRAP_FORCE_LOGGING:-0}"
  if { [ -t 1 ] && [ -t 2 ]; } && [ "$FORCE_LOG" != "1" ]; then
    : # Skip tee logging to avoid breaking Claude Code interactive mode
  else
    exec > >(tee -a "$CLAUDE_LOG_FILE")
    exec 2> >(tee -a "$CLAUDE_LOG_FILE" >&2)
  fi
fi

CLAUDE_LOGGING_ACTIVE=0
if [ "${CLAUDE_WRAP_ENABLE_LOGGING:-1}" = "1" ]; then
  exec {CLAUDE_LOG_FD}>>"$CLAUDE_LOG_FILE"
  {
    printf -- '\n--- claude_wrap start %s pid=%d ---\n' "$(date -Is)" "$$"
  } >&$CLAUDE_LOG_FD
  CLAUDE_LOGGING_ACTIVE=1

  BASH_XTRACEFD=$CLAUDE_LOG_FD
  PS4='+ [claude_wrap] '
  set -o xtrace
fi

claude_wrap_on_exit() {
  local rc=$?
  if [ "${CLAUDE_LOGGING_ACTIVE:-0}" = "1" ]; then
    set +o xtrace
    printf -- '--- claude_wrap end %s pid=%d exit=%d ---\n' "$(date -Is)" "$$" "$rc" >&$CLAUDE_LOG_FD
  fi
  return "$rc"
}
trap claude_wrap_on_exit EXIT

# Configuration loading
load_config() {
    local config_dir="${LLMC_CONFIG_DIR:-$SCRIPT_ROOT/config}"
    local config_script="$config_dir/config.py"
    
    if [ -f "$config_script" ]; then
        # Try to load configuration using Python
        if command -v python3 >/dev/null 2>&1; then
            # Export key configuration as environment variables
            eval "$("$PYTHON_BIN" "$config_script" --export-shell 2>/dev/null || true)"
        fi
    fi
}

# Load configuration early
load_config

# Usage/help
print_claude_wrap_help() {
  cat <<'EOF'
Usage: scripts/claude_wrap.sh [options] [prompt|prompt_file]

Options:
  -l, --local          Force routing to local Ollama profile
  -a, --api            Force routing to remote API profile (Gemini)
  -c, --claude         Force routing directly to Claude Code
  -ca,--claude-azure   Force routing to Claude Code with Azure OpenAI
  -m, --minimax        Force routing to MiniMax M2 API (text mode)
  -t, --tui BACKEND    Launch TUI with specified backend
      --template       Launch Template Builder TUI
      --azure          Use Azure OpenAI backend for Claude
      --repo PATH      Run against a different repository root
      --dangerously-skip-permissions
                       Bypass all permission checks (dangerous!)
  -y, --yolo          YOLO mode - works with all other options
  -h, --help          Show this help message and exit

TUI Backends:
  --tui minimax        TUI with MiniMax backend
  --tui claude         TUI with Claude backend
  --tui azure          TUI with Azure OpenAI backend
  --tui gemini         TUI with Gemini backend
  --template           Template Builder TUI (interactive bundle generator)

Environment Variables:
  CLAUDE_SETTINGS      Path to Claude settings.json (for Azure)
  AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT
  ANTHROPIC_API_KEY    Claude API key (if not using Azure)
  CLAUDE_WRAP_DISABLE_RAG  Set to 1 to disable RAG context
  SEMANTIC_CACHE_ENABLE  Set to 1 to enable semantic caching
  DEEP_RESEARCH_ENABLED  Set to 1 to enable deep research detection

Examples:
  scripts/claude_wrap.sh --local "Fix the failing unit test"
  scripts/claude_wrap.sh --azure "Add user authentication"
  scripts/claude_wrap.sh --yolo "Deploy everything now!"  # YOLO mode bypasses checks
  scripts/claude_wrap.sh --dangerously-skip-permissions "Force execute task"
  scripts/claude_wrap.sh --yolo --local "YOLO with routing"  # Works with other options
  scripts/claude_wrap.sh --tui minimax  # Launch interactive TUI with MiniMax
  scripts/claude_wrap.sh --tui claude   # Launch interactive TUI with Claude
  scripts/claude_wrap.sh --tui azure    # Launch interactive TUI with Azure
  scripts/claude_wrap.sh --template     # Launch Template Builder TUI
  scripts/claude_wrap.sh --repo ../other/repo task.txt
EOF
}

# Default summary lengths (override via CONTRACT_SUMMARY_LINES / AGENTS_SUMMARY_LINES)
CONTRACT_SUMMARY_LINES="${CONTRACT_SUMMARY_LINES:-60}"
AGENTS_SUMMARY_LINES="${AGENTS_SUMMARY_LINES:-60}"

# Cache directory for reused context slices
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/claude_wrap"
if ! mkdir -p "$CACHE_DIR" 2>/dev/null; then
  CACHE_DIR="$ROOT/.cache/codex_wrap"
  mkdir -p "$CACHE_DIR"
fi

CACHE_LOOKUP_RESULT=""
CACHE_LOOKUP_STATUS="disabled"
CACHE_LOOKUP_SCORE=""

DEEP_RESEARCH_RECOMMENDED=0
DEEP_RESEARCH_RESULT_JSON=""
DEEP_RESEARCH_REMINDER=""
DEEP_RESEARCH_ROUTE_OVERRIDE=0

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

resolve_rag_index_path() {
  # Use configuration system for RAG index path
  local config_dir="${LLMC_CONFIG_DIR:-$SCRIPT_ROOT/config}"
  local config_script="$config_dir/config.py"
  
  if [ -f "$config_script" ] && command -v python3 >/dev/null 2>&1; then
    # Try to get index path from configuration
    local index_path
    if index_path=$("$PYTHON_BIN" "$config_script" --get storage.index_path 2>/dev/null); then
      # Expand relative paths
      if [[ "$index_path" == .* ]]; then
        index_path="$ROOT/$index_path"
      elif [[ "$index_path" != /* ]]; then
        index_path="$ROOT/$index_path"
      fi
      
      if [ -f "$index_path" ]; then
        echo "$index_path"
        return 0
      fi
    fi
  fi
  
  # Fall back to environment variable or default paths
  local candidate="${LLMC_RAG_INDEX_PATH:-$ROOT/.rag/index_v2.db}"
  if [ -f "$candidate" ]; then
    echo "$candidate"
    return 0
  fi
  candidate="$ROOT/.rag/index.db"
  if [ -f "$candidate" ]; then
    echo "$candidate"
    return 0
  fi
  return 1
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

semantic_cache_enabled() {
  if [ "${SEMANTIC_CACHE_DISABLE:-0}" = "1" ]; then
    return 1
  fi
  if [ "${SEMANTIC_CACHE_ENABLE:-1}" = "0" ]; then
    return 1
  fi
  return 0
}

semantic_cache_provider() {
  echo "${ANTHROPIC_MODEL:-claude-sonnet-4-20250514}"
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

rag_plan_snippet() {
  local user_query="$1"
  if [ "${CLAUDE_WRAP_DISABLE_RAG:-0}" = "1" ]; then
    return 0
  fi
  local index_path
  if ! index_path="$(resolve_rag_index_path)"; then
    return 0
  fi
  local script="$ROOT/scripts/rag_plan_snippet.py"
  if [ ! -x "$script" ]; then
    return 0
  fi
  local output
  if ! output=$(LLMC_RAG_INDEX_PATH="$index_path" "$PYTHON_BIN" "$script" --repo "$ROOT" --limit "${RAG_PLAN_LIMIT:-5}" --min-score "${RAG_PLAN_MIN_SCORE:-0.4}" --min-confidence "${RAG_PLAN_MIN_CONFIDENCE:-0.6}" --no-log <<<"$user_query" 2>/dev/null); then
    [ -n "${CODEX_WRAP_DEBUG:-}" ] && echo "claude_wrap: rag plan failed" >&2
    return 0
  fi
  output="$(printf '%s' "$output" | sed '/^[[:space:]]*$/d')"
  if [ -n "$output" ]; then
    printf '%s\n' "$output"
  fi
}

# -------------------------------------------------------------------
# Contract bootstrap: authoritative directives shown to the model
# -------------------------------------------------------------------
bootstrap_contract() {
  cat <<'EOF'
bootstrap_contract() {
  cat <<'EOF'
<bootstrap_contract>
AUTHORITY & PRECEDENCE
- Session directives from Dave > AGENTS.md > CONTRACTS.md.
- On conflict: STOP and report the mismatch.

COMPLIANCE (MANDATORY)
- Read and OBEY AGENTS.md (ops). Then read CONTRACTS.md (env).
- Confirm understanding BEFORE any action.
- While PLANNING ON: no reads (without ALLOW), no writes, no tools, no exec.

## ENGAGE Protocol (compact)

Precedence: Session > AGENTS.md > CONTRACTS.md
Default: PLANNING ON, MODE: STEP

Digest (wrapper inserts): v=<n> A=<sha_ag> C=<sha_ct>
Model must echo: ECHO v=<n> A=<sha_ag> C=<sha_ct> OK

Permissions (default DENY)
- REQ: READ <paths|globs>
- ALLOW: READ <paths>
- No scans/tool-dumps/net calls without ALLOW.

States: PLANNING ON | PLANNING OFF | EXEC | POST | BLOCKED | VIOLATION
Mode: ALL | STEP   (set with: MODE: ALL or MODE: STEP)

Commands (aliases)
- PLANNING ON        (planning only; no exec)
- PLANNING OFF       (planning complete; ready to run)
- MODE: ALL          (ENGAGE runs all approved steps)
- MODE: STEP         (ENGAGE runs the next step only)
- ENGAGE             (run per MODE)
- DISENGAGE          (abort; return to PLANNING ON)
- STOP               (immediate stop)

Planner output (required while PLANNING ON)
READINESS: files=AGENTS,CONTRACTS(if allowed); precedence=Session>AGENTS>CONTRACTS; constraints=scope:1file/50LOC,testing:AGENTS,installs:deny; read_perms=<granted|none>; mode=<ALL|STEP>
PLAN:
- STEP 1: <exact change>
- STEP 2: <exact change>
- STEP 3: <exact change>
RISKS:
- <risk 1>
- <risk 2>
- <risk 3>
AWAITING PLANNING OFF

Execution rules
- After PLANNING OFF:
  - MODE=ALL: ENGAGE executes all steps in order; halt on first failure.
  - MODE=STEP: ENGAGE executes the next step only; then STOP and print AWAITING ENGAGE.
- After each run, output:
  SUMMARY (<=3 lines)
  DIFF (changed files only)
  TESTS: PASSED | FAILED:<why> | SKIPPED:<why>
  NEXT (<=3 bullets)

Guards (fail-closed)
- Missing/extra/changed markers -> BLOCKED:<reason>
- Reads without ALLOW -> BLOCKED:read
- Exceeds scope (>1 file or >50 LOC) -> BLOCKED:scope
- Tests impossible -> TESTING SKIPPED:<reason> and STOP
- Plan modified mid-run or out-of-order -> VIOLATION
- Timebox ~2m; need tmux? ask first.

VIOLATION
Ignoring any rule above = mission failure. If unsure, STOP and ask.
</bootstrap_contract>
EOF
}


# Build the prompt
build_prompt() {
  local prompt=""

  # Include bootstrap contract FIRST (highest authority)
  prompt="$(bootstrap_contract)

---

"

  local contract_sections="${CONTRACT_SECTIONS:-}"
  local agents_sections="${AGENTS_SECTIONS:-}"

  # Load AGENTS.md FIRST (operational rules)
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

  # Load CONTRACTS.md SECOND (environment/policies)
  local contract_context=""
  if [ -f "$CONTRACT" ]; then
    contract_context="$(load_doc_context contract "$CONTRACT" "$CONTRACT_SUMMARY_LINES" "$contract_sections")"
  else
    echo "⚠️  Warning: CONTRACTS.md not found at $CONTRACT" >&2
  fi

  if [ -n "$contract_context" ]; then
    prompt="$prompt$contract_context

---

"
  fi

  local rag_context
  rag_context=$(rag_plan_snippet "$1") || rag_context=""
  if [ -n "$rag_context" ]; then
    prompt="$prompt$rag_context

---

"
  fi

  prompt="$prompt<otto_directive>\nCRITICAL: You are Otto, a methodical and analytical AI assistant. Approach each task with careful consideration, prioritizing correctness and clarity. Provide thorough explanations when beneficial, but remain concise when brevity serves the goal better. Always validate assumptions before proceeding.\n</otto_directive>\n\n---\n\n"
  prompt="$prompt$1"
  echo "$prompt"
}

# Check if Azure OpenAI is available
azure_available() {
  [ -n "${AZURE_OPENAI_ENDPOINT:-}" ] && [ -n "${AZURE_OPENAI_KEY:-}" ] && [ -n "${AZURE_OPENAI_DEPLOYMENT:-}" ]
}

# Create TUI settings file for specified backend
create_tui_settings() {
  local backend="$1"
  local settings_file="${CLAUDE_SETTINGS:-$HOME/.claude/${backend}-settings.json}"

  if [ -f "$settings_file" ]; then
    echo "$settings_file"
    return 0
  fi

  mkdir -p "$(dirname "$settings_file")"

  case "$backend" in
    minimax)
      if ! [ -n "${MINIMAXKEY2:-}" ]; then
        return 1
      fi
      cat > "$settings_file" <<SETTINGS_EOF
{
  "apiProvider": "openai-compatible",
  "openaiCompatible": {
    "baseURL": "${MINIMAX_BASE_URL:-https://api.minimax.chat/v1}/text/chatcompletion_v2",
    "apiKey": "${MINIMAXKEY2}",
    "defaultHeaders": {
      "Authorization": "Bearer ${MINIMAXKEY2}"
    },
    "defaultParams": {
      "model": "${MINIMAX_MODEL:-abab6-chat}",
      "temperature": 0.7,
      "top_p": 0.95
    }
  }
}
SETTINGS_EOF
      ;;
    azure)
      if ! azure_available; then
        return 1
      fi
      cat > "$settings_file" <<SETTINGS_EOF
{
  "apiProvider": "openai-compatible",
  "openaiCompatible": {
    "baseURL": "${AZURE_OPENAI_ENDPOINT}/openai/deployments/${AZURE_OPENAI_DEPLOYMENT}",
    "apiKey": "${AZURE_OPENAI_KEY}",
    "defaultHeaders": {
      "api-key": "${AZURE_OPENAI_KEY}"
    },
    "defaultParams": {
      "api-version": "${AZURE_OPENAI_API_VERSION:-2024-02-15-preview}"
    }
  }
}
SETTINGS_EOF
      ;;
    gemini)
      # Note: This would need gemini CLI to be configured separately
      echo "Note: For Gemini TUI, ensure 'gemini' CLI is properly configured" >&2
      return 1
      ;;
    claude)
      # No settings needed, uses default Claude
      echo "$settings_file"
      return 0
      ;;
    *)
      return 1
      ;;
  esac

  echo "$settings_file"
  return 0
}

# Create Azure settings file for Claude Code
create_azure_settings() {
  local azure_settings="${CLAUDE_SETTINGS:-$HOME/.claude/azure-settings.json}"

  if [ -f "$azure_settings" ]; then
    echo "$azure_settings"
    return 0
  fi

  if ! azure_available; then
    return 1
  fi

  mkdir -p "$(dirname "$azure_settings")"
  cat > "$azure_settings" <<SETTINGS_EOF
{
  "apiProvider": "openai-compatible",
  "openaiCompatible": {
    "baseURL": "${AZURE_OPENAI_ENDPOINT}/openai/deployments/${AZURE_OPENAI_DEPLOYMENT}",
    "apiKey": "${AZURE_OPENAI_KEY}",
    "defaultHeaders": {
      "api-key": "${AZURE_OPENAI_KEY}"
    },
    "defaultParams": {
      "api-version": "${AZURE_OPENAI_API_VERSION:-2024-02-15-preview}"
    }
  }
}
SETTINGS_EOF

  echo "$azure_settings"
  return 0
}

# Deep research detection
detect_deep_research() {
  local prompt="$1"

  if [ "${DEEP_RESEARCH_ENABLED:-0}" != "1" ]; then
    return 0
  fi

  # Keywords that suggest deep research is needed
  local keywords=(
    "architecture" "design" "security" "compliance" "audit"
    "performance" "scalability" "infrastructure" "migration"
    "refactor" "restructure" "framework" "system design"
  )

  local prompt_lower=$(echo "$prompt" | tr '[:upper:]' '[:lower:]')

  for keyword in "${keywords[@]}"; do
    if [[ "$prompt_lower" == *"$keyword"* ]]; then
      DEEP_RESEARCH_RECOMMENDED=1
      DEEP_RESEARCH_REMINDER="💡 This task may benefit from deep research. Consider documenting findings in research/incoming/"
      echo "$DEEP_RESEARCH_REMINDER" >&2

      if [ -f "$ROOT/logs/deep_research.log" ]; then
        echo "[$(date -Is)] $prompt" >> "$ROOT/logs/deep_research.log"
      fi

      return 0
    fi
  done

  return 0
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

  if [ "${FORCE_CLAUDE_AZURE:-0}" = "1" ]; then
    echo "claude-azure"
    return
  fi

  if [ "${FORCE_CLAUDE:-0}" = "1" ]; then
    echo "claude"
    return
  fi

  if [ "${FORCE_MINIMAX:-0}" = "1" ]; then
    echo "minimax"
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

3. "minimax" - MiniMax M2 API (cost-effective, good for code)
   - Use for: Code generation, refactoring, complex logic, up to 5 files
   - Criteria: ≤5 files, ≤100 lines, moderate risk, some architectural impact

4. "claude" - Premium Claude Code (subscription, best quality)
   - Use for: Complex tasks, architecture, multi-file refactors, new features
   - Criteria: >5 files OR >100 lines OR high risk OR unclear scope

Rules:
- When uncertain, choose "claude" (better safe than sorry)
- Consider: files touched, complexity, risk, architectural impact
- Be conservative: prefer quality over cost savings

Return ONLY valid JSON (no markdown, no backticks):
{
  "route": "local|api|minimax|claude",
  "reason": "one sentence explaining why",
  "confidence": 0.9
}
EOF
)

  # Use API for routing decision (fast, cheap, accurate)
  local decision=$(echo "$routing_prompt" | "$EXEC_ROOT/scripts/llm_gateway.sh" --api 2>/dev/null || echo '{"route":"claude","reason":"routing failed","confidence":0.0}')

  # Parse JSON (handle cases where it might be wrapped in markdown)
  decision=$(echo "$decision" | sed 's/```json//g' | sed 's/```//g' | tr -d '\n' | xargs)

  # Extract route with fallback
  local route=$(echo "$decision" | jq -r '.route // "claude"' 2>/dev/null || echo "claude")
  local reason=$(echo "$decision" | jq -r '.reason // "unknown"' 2>/dev/null || echo "routing decision made")
  local confidence=$(echo "$decision" | jq -r '.confidence // 0.5' 2>/dev/null || echo "0.5")

  echo "📊 Decision: $route (confidence: $confidence)" >&2
  echo "💡 Reason: $reason" >&2
  echo "" >&2

  if [ "${DEEP_RESEARCH_RECOMMENDED:-0}" = "1" ] && [ "${DEEP_RESEARCH_ALLOW_AUTO:-0}" != "1" ]; then
    if [ "$route" != "local" ]; then
      echo "🔒 Deep research gating: overriding route to 'local' until research notes are ingested. Set DEEP_RESEARCH_ALLOW_AUTO=1 to bypass." >&2
      route="local"
      DEEP_RESEARCH_ROUTE_OVERRIDE=1
    fi
  fi

  echo "$route"
}

# Execute the prompt
execute_route() {
  local route="$1"
  local user_prompt="$2"
  local full_prompt=$(build_prompt "$user_prompt")
  local provider="claude"
  
  # Build Claude flags based on YOLO mode
  local claude_flags="--print"
  if [ "${YOLO_MODE:-0}" = "1" ] || [ "${DANGEROUSLY_SKIP_PERMISSIONS:-0}" = "1" ]; then
    claude_flags="--print --dangerously-skip-user-confirmation"
  fi
  
  # Build Claude flags based on YOLO mode
  local claude_flags="--print"
  if [ "${YOLO_MODE:-0}" = "1" ] || [ "${DANGEROUSLY_SKIP_PERMISSIONS:-0}" = "1" ]; then
    claude_flags="--print --dangerously-skip-user-confirmation"
  fi
  
  # Build Claude flags based on YOLO mode
  local claude_flags="--print"
  if [ "${YOLO_MODE:-0}" = "1" ] || [ "${DANGEROUSLY_SKIP_PERMISSIONS:-0}" = "1" ]; then
    claude_flags="--print --dangerously-skip-user-confirmation"
  fi
  
  # Build Claude flags based on YOLO mode
  local claude_flags="--print"
  if [ "${YOLO_MODE:-0}" = "1" ] || [ "${DANGEROUSLY_SKIP_PERMISSIONS:-0}" = "1" ]; then
    claude_flags="--print --dangerously-skip-user-confirmation"
  fi
  
  # Build Claude flags based on YOLO mode
  local claude_flags="--print"
  if [ "${YOLO_MODE:-0}" = "1" ] || [ "${DANGEROUSLY_SKIP_PERMISSIONS:-0}" = "1" ]; then
    claude_flags="--print --dangerously-skip-user-confirmation"
  fi
  
  # Build Claude flags based on YOLO mode
  local claude_flags="--print"
  if [ "${YOLO_MODE:-0}" = "1" ] || [ "${DANGEROUSLY_SKIP_PERMISSIONS:-0}" = "1" ]; then
    claude_flags="--print --dangerously-skip-user-confirmation"
  fi
  
  # Build Claude flags based on YOLO mode
  local claude_flags="--print"
  if [ "${YOLO_MODE:-0}" = "1" ] || [ "${DANGEROUSLY_SKIP_PERMISSIONS:-0}" = "1" ]; then
    claude_flags="--print --dangerously-skip-user-confirmation"
  fi

  # Update provider based on route
  case "$route" in
    local) provider="ollama" ;;
    api) provider="gemini" ;;
    minimax) provider="minimax" ;;
    claude-azure) provider="azure" ;;
    claude|*) provider="claude" ;;
  esac

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
      response=$(RAG_USER_PROMPT="$user_prompt" "$EXEC_ROOT/scripts/llm_gateway.sh" --api <<<"$full_prompt")
      status=$?
      ;;

    minimax)
      echo "🌐 Routing to MiniMax API..." >&2
      response=$(RAG_USER_PROMPT="$user_prompt" "$EXEC_ROOT/scripts/llm_gateway.sh" --minimax <<<"$full_prompt")
      status=$?
      ;;

    claude-azure)
      if ! azure_available; then
        echo "❌ Azure environment variables missing; cannot honor --claude-azure/-ca." >&2
        return 1
      fi
      echo "🧠 Routing to Claude Code with Azure OpenAI (forced)..." >&2

      local azure_settings
      if ! azure_settings=$(create_azure_settings); then
        echo "❌ Failed to create Azure settings file" >&2
        return 1
      fi

      response=$(printf '%s\n' "$full_prompt" | claude --settings "$azure_settings" $claude_flags -)
      status=$?
      ;;

    claude|*)
      if [ "${USE_AZURE:-0}" = "1" ] && azure_available; then
        echo "🧠 Routing to Claude Code with Azure OpenAI..." >&2

        local azure_settings
        if ! azure_settings=$(create_azure_settings); then
          echo "⚠️  Failed to create Azure settings, falling back to Claude Code (web auth)..." >&2
          response=$(printf '%s\n' "$full_prompt" | claude $claude_flags -)
          status=$?
        else
          response=$(printf '%s\n' "$full_prompt" | claude --settings "$azure_settings" $claude_flags -)
          status=$?
        fi
      else
        echo "🧠 Routing to Claude Code (web auth)..." >&2
        response=$(printf '%s\n' "$full_prompt" | claude $claude_flags -)
        status=$?
      fi
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

  CACHE_LOOKUP_RESULT=""
  return $status
}

# Main execution
USER_PROMPT=""
FORCE_LOCAL=0
FORCE_API=0
FORCE_CLAUDE=0
FORCE_CLAUDE_AZURE=0
FORCE_MINIMAX=0
FORCE_TUI_BACKEND=""
LAUNCH_TEMPLATE_TUI=0
USE_AZURE=0
ENABLE_ROUTING=${ENABLE_ROUTING:-0}
DANGEROUSLY_SKIP_PERMISSIONS=0
YOLO_MODE=0

# Early argument parsing for bypass flags (before permission checks)
for arg in "$@"; do
  case "$arg" in
    --dangerously-skip-permissions)
      DANGEROUSLY_SKIP_PERMISSIONS=1
      ;;
    -y|--yolo)
      YOLO_MODE=1
      ;;
  esac
done

# Load environment flags for LLM disable
if [ -f "$ROOT/.env.local" ]; then
  while IFS='=' read -r k v; do
    case "$k" in
      LLM_DISABLED|NEXT_PUBLIC_LLM_DISABLED|WEATHER_DISABLED)
        v="${v%\'}"
        v="${v#\'}"
        v="${v%\"}"
        v="${v#\"}"
        export "$k"="$v"
        ;;
    esac
  done < <(grep -E '^(LLM_DISABLED|NEXT_PUBLIC_LLM_DISABLED|WEATHER_DISABLED)=' "$ROOT/.env.local" 2>/dev/null || true)
fi

to_bool() {
  case "$(echo "$1" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on) return 0;;
    *) return 1;;
  esac
}

# Default-disabled when no flags are present
# Skip permission checks if dangerously-skip-permissions or yolo mode is enabled
if [ "$DANGEROUSLY_SKIP_PERMISSIONS" != "1" ] && [ "$YOLO_MODE" != "1" ]; then
  # Only apply the default-disabled check if routing is not explicitly enabled and bypass flags are not set
  if [ "$ENABLE_ROUTING" != "1" ] && [ "$DANGEROUSLY_SKIP_PERMISSIONS" != "1" ] && [ "$YOLO_MODE" != "1" ]; then
    if to_bool "${LLM_DISABLED:-}" || to_bool "${NEXT_PUBLIC_LLM_DISABLED:-}" || to_bool "${WEATHER_DISABLED:-}"; then
      echo "🧯 LLM features are disabled via environment (LLM_DISABLED / NEXT_PUBLIC_LLM_DISABLED / WEATHER_DISABLED)." >&2
      echo "Set LLM_DISABLED=false to re-enable." >&2
      exit 0
    fi
    # Default-disabled when no env vars are set and no flags present
    if [ -z "${LLM_DISABLED:-}" ] && [ -z "${NEXT_PUBLIC_LLM_DISABLED:-}" ] && [ -z "${WEATHER_DISABLED:-}" ]; then
      echo "🧯 LLM features are disabled by default. Set LLM_DISABLED=false to re-enable." >&2
      exit 0
    fi
  fi
fi

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --local|-l)
      FORCE_LOCAL=1
      ENABLE_ROUTING=1
      shift
      ;;
    --api|-a)
      FORCE_API=1
      ENABLE_ROUTING=1
      shift
      ;;
    --claude|-c)
      FORCE_CLAUDE=1
      shift
      ;;
    --claude-azure|-ca)
      FORCE_CLAUDE_AZURE=1
      shift
      ;;
    --minimax|-m)
      FORCE_MINIMAX=1
      ENABLE_ROUTING=1
      shift
      ;;
    --tui|-t)
      if [[ $# -gt 1 ]]; then
        FORCE_TUI_BACKEND="$2"
        shift 2
      else
        echo "Error: --tui requires a backend parameter" >&2
        echo "Usage: --tui minimax|claude|azure|gemini" >&2
        exit 1
      fi
      ;;
    --tui=*)
      FORCE_TUI_BACKEND="${1#--tui=}"
      shift
      ;;
    --template)
      LAUNCH_TEMPLATE_TUI=1
      shift
      ;;
    --azure)
      USE_AZURE=1
      shift
      ;;
    --route)
      ENABLE_ROUTING=1
      shift
      ;;
    --repo)
      shift  # Already handled in pre-scan
      shift
      ;;
    --repo=*)
      shift  # Already handled in pre-scan
      ;;
    --dangerously-skip-permissions)
      DANGEROUSLY_SKIP_PERMISSIONS=1
      shift
      ;;
    -y|--yolo)
      YOLO_MODE=1
      shift
      ;;
    --help|-h)
      print_claude_wrap_help
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      print_claude_wrap_help
      exit 1
      ;;
    *)
      if [ -f "$1" ]; then
        USER_PROMPT="$(cat -- "$1")"
      else
        if [ -z "$USER_PROMPT" ]; then
          USER_PROMPT="$1"
        else
          USER_PROMPT="$USER_PROMPT $1"
        fi
      fi
      shift
      ;;
  esac
done

USER_PROMPT=$(echo "$USER_PROMPT" | xargs)

# Read from stdin if no prompt and stdin is available
if [ -z "$USER_PROMPT" ] && [ ! -t 0 ]; then
  USER_PROMPT="$(cat)"
fi

# If still no prompt, use interactive mode
if [ -z "$USER_PROMPT" ]; then
  # Handle TUI with specified backend
  if [ -n "$FORCE_TUI_BACKEND" ]; then
    echo "🧠 Starting TUI with ${FORCE_TUI_BACKEND} backend and context management..." >&2

    if ! tui_settings=$(create_tui_settings "$FORCE_TUI_BACKEND"); then
      case "$FORCE_TUI_BACKEND" in
        minimax)
          echo "❌ Failed to create MiniMax settings file" >&2
          echo "Make sure MINIMAXKEY2 is set in your environment" >&2
          ;;
        azure)
          echo "❌ Failed to create Azure settings file" >&2
          echo "Make sure AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, and AZURE_OPENAI_DEPLOYMENT are set" >&2
          ;;
        gemini)
          echo "❌ Gemini TUI requires proper 'gemini' CLI configuration" >&2
          ;;
        *)
          echo "❌ Failed to create TUI settings for $FORCE_TUI_BACKEND" >&2
          ;;
      esac
      exit 1
    fi

    if [ "$FORCE_TUI_BACKEND" = "claude" ]; then
      # No settings file needed for default Claude
      claude
    else
      claude --settings "$tui_settings"
    fi
    exit $?
  fi

  # Handle Template Builder TUI
  if [ "$LAUNCH_TEMPLATE_TUI" = "1" ]; then
    echo "🚀 Starting Template Builder TUI..." >&2
    exec "$SCRIPT_ROOT/scripts/template_builder_tui.sh"
    exit $?
  fi

  # Check if any routing flags are set - if so, use routing with empty prompt
  if [ "$ENABLE_ROUTING" = "1" ]; then
    echo "🧠 Starting with routing enabled..." >&2
    ROUTE=$(route_task "")
    execute_route "$ROUTE" ""
    exit $?
  else
    echo "🧠 Starting Claude Code in interactive mode..." >&2
    claude
    exit $?
  fi
fi

# Detect deep research needs
detect_deep_research "$USER_PROMPT"

# Route and execute
if [ "$ENABLE_ROUTING" = "1" ]; then
  ROUTE=$(route_task "$USER_PROMPT")
  execute_route "$ROUTE" "$USER_PROMPT"
else
  # Default behavior: use Claude without routing
  execute_route "claude" "$USER_PROMPT"
fi
