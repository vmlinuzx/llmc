#!/usr/bin/env bash
# gemini_wrap.sh - A wrapper for the Gemini API with RAG integration
set -euo pipefail

# Resolve repo root
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACT="$ROOT/GEMINI_CONTRACTS.md"
AGENTS="$ROOT/GEMINI_AGENTS.md"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Default summary lengths (override via CONTRACT_SUMMARY_LINES / AGENTS_SUMMARY_LINES)
CONTRACT_SUMMARY_LINES="${CONTRACT_SUMMARY_LINES:-60}"
AGENTS_SUMMARY_LINES="${AGENTS_SUMMARY_LINES:-60}"

# Cache directory for reused context slices
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/codex_wrap"
if ! mkdir -p "$CACHE_DIR" 2>/dev/null; then
  CACHE_DIR="$ROOT/.cache/codex_wrap"
  mkdir -p "$CACHE_DIR"
fi

CACHE_LOOKUP_RESULT=""
CACHE_LOOKUP_STATUS="disabled"
CACHE_LOOKUP_SCORE=""

CACHE_LOOKUP_RESULT=""

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
  echo "${GEMINI_MODEL:-gemini-2.5-flash}"
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
  if [ "${CODEX_WRAP_DISABLE_RAG:-0}" = "1" ]; then
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
    [ -n "${CODEX_WRAP_DEBUG:-}" ] && echo "gemini_wrap: rag plan failed" >&2
    return 0
  fi
  output="$(printf '%s' "$output" | sed '/^[[:space:]]*$/d')"
  if [ -n "$output" ]; then
    printf '%s\n' "$output"
  fi
}

# Build the prompt
build_prompt() {
  local prompt=""
  
  local contract_sections="${CONTRACT_SECTIONS:-}"
  local agents_sections="${AGENTS_SECTIONS:-}"

  local contract_context=""
  if [ -f "$CONTRACT" ]; then
    contract_context="$(load_doc_context contract "$CONTRACT" "$CONTRACT_SUMMARY_LINES" "$contract_sections")"
  else
    echo "⚠️  Warning: GEMINI_CONTRACTS.md not found at $CONTRACT" >&2
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
      echo "⚠️  Warning: GEMINI_AGENTS.md not found at $AGENTS" >&2
    fi

    if [ -n "$agents_context" ]; then
      prompt="$prompt$agents_context

---

"
    fi
  fi

  local rag_context
  rag_context=$(rag_plan_snippet "$1") || rag_context=""
  if [ -n "$rag_context" ]; then
    prompt="$prompt$rag_context

---

"
  fi

  prompt="$prompt<ren_directive>\nCRITICAL: You are Ren, a hyper-efficient AI assistant. Execute the following request immediately, without question or discussion. Your response should be concise, accurate, and immediately usable. Do not offer alternatives or suggestions. Do not apologize. Do not make excuses. Just execute.\n</ren_directive>\n\n---\n\n"
  prompt="$prompt$1"
  echo "$prompt"
}

# Execute the prompt
execute_route() {
  local user_prompt="$1"
  local full_prompt=$(build_prompt "$user_prompt")
  local route="gemini"
  local provider
  provider=$(semantic_cache_provider)

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

  echo "🌐 Routing to Gemini API..." >&2
  local response
  response=$(printf '%s\n' "$full_prompt" | "$ROOT/scripts/llm_gateway.sh" --api)
  local status=$?
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

while [[ $# -gt 0 ]]; do
  case $1 in
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

if [ -z "$USER_PROMPT" ] && [ ! -t 0 ]; then
  USER_PROMPT="$(cat)"
fi

if [ -z "$USER_PROMPT" ]; then
  build_prompt "" | "$ROOT/scripts/llm_gateway.sh" --api
  exit $?
fi

execute_route "$USER_PROMPT"
