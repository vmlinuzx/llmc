#!/usr/bin/env bash
set -euo pipefail

# Read full response from stdin
resp=$(cat)

extract_json_block() {
  # Grab the last ```json ... ``` fenced block
  awk '
    BEGIN{f=0}
    /^```json[ \t]*$/{f=1;buf="";next}
    /^```[ \t]*$/{if(f==1){last=buf} f=0;next}
    { if(f==1){buf = buf $0 ORS} }
    END{ if (last) print last }
  '
}

call_tool_from_json() {
  local js="$1"
  local name
  name=$(printf '%s' "$js" | jq -r '(.name // .tool) // empty' 2>/dev/null || true)
  if [ -z "${name:-}" ]; then return 1; fi
  case "$name" in
    search_tools)
      local q
      q=$(printf '%s' "$js" | jq -r '.arguments.query // empty' 2>/dev/null || true)
      [ -z "${q:-}" ] && return 1
      python3 "$(dirname "$0")/tool_query.py" search "$q"
      ;;
    describe_tool)
      local n
      n=$(printf '%s' "$js" | jq -r '.arguments.name // empty' 2>/dev/null || true)
      [ -z "${n:-}" ] && return 1
      python3 "$(dirname "$0")/tool_query.py" describe "$n"
      ;;
    *)
      return 1
      ;;
  esac
}

# Try JSON fenced block
json_block=$(printf '%s' "$resp" | extract_json_block || true)
if [ -n "${json_block:-}" ]; then
  if result=$(call_tool_from_json "$json_block" 2>/dev/null); then
    printf '%s\n\n---\n[Tool Result]\n%s\n' "$resp" "$result"
    exit 0
  fi
fi

# Fallback: detect simple inline forms: search_tools("...") or describe_tool("...")
if grep -qE 'search_tools\s*\(' <<<"$resp"; then
  q=$(printf '%s' "$resp" | sed -n "s/.*search_tools\s*(\s*['\"]\(.*\)['\"].*/\1/p" | head -n1)
  if [ -n "${q:-}" ]; then
    result=$(python3 "$(dirname "$0")/tool_query.py" search "$q" 2>/dev/null || true)
    if [ -n "$result" ]; then printf '%s\n\n---\n[Tool Result]\n%s\n' "$resp" "$result"; exit 0; fi
  fi
fi

if grep -qE 'describe_tool\s*\(' <<<"$resp"; then
  n=$(printf '%s' "$resp" | sed -n "s/.*describe_tool\s*(\s*['\"]\(.*\)['\"].*/\1/p" | head -n1)
  if [ -n "${n:-}" ]; then
    result=$(python3 "$(dirname "$0")/tool_query.py" describe "$n" 2>/dev/null || true)
    if [ -n "$result" ]; then printf '%s\n\n---\n[Tool Result]\n%s\n' "$resp" "$result"; exit 0; fi
  fi
fi

# Default: pass-through
printf '%s' "$resp"

