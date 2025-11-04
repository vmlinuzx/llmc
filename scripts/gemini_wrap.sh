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
  
  echo "🌐 Routing to Gemini API..." >&2
  echo "$full_prompt" | "$ROOT/scripts/llm_gateway.sh" --api
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