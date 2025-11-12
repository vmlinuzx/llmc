#!/usr/bin/env bash
set -euo pipefail
shopt -s globstar

CHANGESET_JSON=""
TARGET_BRANCH="${TARGET_BRANCH:-main}"
LEASE_TTL="${LEASE_TTL_SECONDS:-600}"
LOCK_BACKOFF_MS="${LOCK_BACKOFF_MS:-750}"
LOCK_MAX_RETRIES="${LOCK_MAX_RETRIES:-40}"
SAFE_LANES="${SAFE_LANES:-}"
SHADOW_MODE="${LLMC_SHADOW_MODE:-off}"
GATE_TIMEOUT="${LLMC_GATE_TIMEOUT_SECONDS:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --changeset) CHANGESET_JSON="$2"; shift 2;;
    *) echo "unknown arg $1"; exit 64;;
  esac
done
[ -f "$CHANGESET_JSON" ] || { echo "ChangeSet JSON required"; exit 64; }

ID=$(jq -r '.id' "$CHANGESET_JSON")
BASE=$(jq -r '.base_commit' "$CHANGESET_JSON")
DIFF_FILE=$(mktemp)
jq -r '.diff' "$CHANGESET_JSON" > "$DIFF_FILE"
PLAN_JSON=$(mktemp); jq -r '.validation_plan' "$CHANGESET_JSON" > "$PLAN_JSON"
mapfile -t LOCKS < <(jq -r '.locks[]' "$CHANGESET_JSON")
STARTED_AT=$(date +%s)

if ! git rev-parse --verify "$TARGET_BRANCH" >/dev/null 2>&1; then
  if git rev-parse --verify "origin/${TARGET_BRANCH}" >/dev/null 2>&1; then
    git branch --track "$TARGET_BRANCH" "origin/${TARGET_BRANCH}" >/dev/null 2>&1 || true
  else
    echo "[integrator] target branch ${TARGET_BRANCH} not found" >&2
    exit 73
  fi
fi

if ! git merge-base --is-ancestor "$BASE" "$TARGET_BRANCH"; then
  echo "[integrator] base commit ${BASE} is not an ancestor of ${TARGET_BRANCH}" >&2
  exit 73
fi

for res in "${LOCKS[@]}"; do
  tries=0
  while true; do
    out=$(python3 llmc/scripts/llmc_lock.py acquire --resource "$res" --task-id "$ID" --ttl "$LEASE_TTL" --started-at "$STARTED_AT" || true)
    status=$(echo "$out" | jq -r '.status // empty')
    if [ "$status" = "ACQUIRED" ] || [ "$status" = "RENEWED" ]; then
      break
    elif [ "$status" = "WOUNDED" ]; then
      sleep "$(awk "BEGIN {print ${LOCK_BACKOFF_MS}/1000}")"
    else
      sleep "$(awk "BEGIN {print ${LOCK_BACKOFF_MS}/1000}")"
    fi
    tries=$((tries+1)); [ $tries -ge $LOCK_MAX_RETRIES ] && echo "lock timeout on $res" >&2 && exit 75
  done
done

WT_DIR=".llmc/worktrees/${ID}"
mkdir -p ".llmc/worktrees" || true
git worktree add -B "llmc/${ID}" "${WT_DIR}" "${BASE}"

( cd "${WT_DIR}" && git apply --index "${DIFF_FILE}" && git commit -m "LLMC ChangeSet ${ID}" || { echo "patch failed"; exit 65; } )

GATE_CMD=(llmc/scripts/integration_gate.sh "${WT_DIR}")
if [ -n "$GATE_TIMEOUT" ]; then
  GATE_CMD=(timeout "$GATE_TIMEOUT" "${GATE_CMD[@]}")
fi

if ! PLAN_JSON="$PLAN_JSON" "${GATE_CMD[@]}"; then
  echo "[integrator] gate failed" >&2
  EXIT_FAIL=1
else
  EXIT_FAIL=0
fi

MERGE_ALLOWED=1
if [ -n "$SAFE_LANES" ]; then
  IFS=',' read -r -a SAFE_PATTERNS <<<"$SAFE_LANES"
  for res in "${LOCKS[@]}"; do
    matched=0
    for pat in "${SAFE_PATTERNS[@]}"; do
      pat_trim=$(printf '%s' "$pat" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
      [ -z "$pat_trim" ] && continue
      if [[ "$res" == $pat_trim ]]; then
        matched=1
        break
      fi
    done
    if [ $matched -eq 0 ]; then
      MERGE_ALLOWED=0
      break
    fi
  done
fi

if [ "$EXIT_FAIL" -eq 0 ] && [ "$SHADOW_MODE" != "on" ] && [ $MERGE_ALLOWED -eq 1 ]; then
  git -C . fetch origin "${TARGET_BRANCH}" || true
  git -C . checkout "${TARGET_BRANCH}"
  git -C . merge --ff-only "llmc/${ID}"
  echo "[integrator] merged to ${TARGET_BRANCH}"
else
  if [ "$EXIT_FAIL" -eq 0 ] && [ "$SHADOW_MODE" = "on" ]; then
    echo "[integrator] shadow mode enabled; merge skipped"
  fi
  if [ $MERGE_ALLOWED -eq 0 ]; then
    echo "[integrator] locks outside SAFE_LANES; merge skipped"
  fi
  echo "[integrator] not merged; leaving branch llmc/${ID} for inspection"
fi

for res in "${LOCKS[@]}"; do
  python3 llmc/scripts/llmc_lock.py release --resource "$res" --task-id "$ID" >/dev/null || true
done

mkdir -p .llmc/logs
TS=$(date -Is)
if [ "$EXIT_FAIL" -eq 0 ] && [ "$SHADOW_MODE" != "on" ] && [ $MERGE_ALLOWED -eq 1 ]; then
  MERGED=true
else
  MERGED=false
fi
printf '{"timestamp":"%s","changeset":"%s","merged":%s,"target_branch":"%s"}\n' \
  "$TS" "$ID" "$MERGED" "$TARGET_BRANCH" >> .llmc/logs/integrations.jsonl

exit $EXIT_FAIL
