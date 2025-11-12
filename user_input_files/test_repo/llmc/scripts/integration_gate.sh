#!/usr/bin/env bash
set -euo pipefail

WORKTREE="${1:-}"
[ -z "$WORKTREE" ] && echo "usage: integration_gate.sh <worktree_path>" >&2 && exit 64

PLAN_JSON="${PLAN_JSON:-}"

jq_get() { jq -r "${2}" "${1}" 2>/dev/null || true; }

if [ -n "${PLAN_JSON}" ] && [ -f "${PLAN_JSON}" ]; then
  FORMAT_CMD=$(jq_get "${PLAN_JSON}" '.format // empty')
  BUILD_CMD=$(jq_get  "${PLAN_JSON}" '.build // empty')
  TESTS_COMBINED=$(jq -r '(.tests // []) | @sh' "${PLAN_JSON}" | sed "s/^'//;s/'$//" || true)
  STATIC_CHECKS_COMBINED=$(jq -r '(.static_checks // []) | @sh' "${PLAN_JSON}" | sed "s/^'//;s/'$//" || true)
else
  FORMAT_CMD="${FORMAT_CMD:-}"
  BUILD_CMD="${BUILD_CMD:-}"
  TESTS_COMBINED="${TESTS_COMBINED:-}"
  STATIC_CHECKS_COMBINED="${STATIC_CHECKS_COMBINED:-}"
fi

run_step () {
  local name="$1" cmd="$2"
  [ -z "$cmd" ] && return 0
  echo "[gate] $name: $cmd"
  (cd "$WORKTREE" && eval "$cmd")
}

if [ -n "$FORMAT_CMD" ]; then
  set +e; run_step "format" "$FORMAT_CMD"; set -e
fi

run_step "build" "${BUILD_CMD}"

if [ -n "$TESTS_COMBINED" ]; then
  IFS=$'\n' read -r -d '' -a TEST_CMDS < <(jq -r '(.tests // [])[]' "${PLAN_JSON}" 2>/dev/null || true; printf '\0')
  if [ "${#TEST_CMDS[@]}" -eq 0 ] && [ -n "${TESTS_COMBINED}" ]; then
    TEST_CMDS=("${TESTS_COMBINED}")
  fi
  for t in "${TEST_CMDS[@]}"; do
    run_step "test" "${t}"
  done
fi

if [ -n "$STATIC_CHECKS_COMBINED" ]; then
  IFS=$'\n' read -r -d '' -a SC_CMDS < <(jq -r '(.static_checks // [])[]' "${PLAN_JSON}" 2>/dev/null || true; printf '\0')
  if [ "${#SC_CMDS[@]}" -eq 0 ] && [ -n "${STATIC_CHECKS_COMBINED}" ]; then
    SC_CMDS=("${STATIC_CHECKS_COMBINED}")
  fi
  for s in "${SC_CMDS[@]}"; do
    run_step "static" "${s}"
  done
fi

echo "[gate] OK"
