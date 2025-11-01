#!/usr/bin/env bash
# =================================================================================================
# sync_to_drive.sh — Hardened, backgrounded one-way mirror to Google Drive via rclone
#
# Purpose:
#   Mirror the repo (respecting .gitignore + .codexignore) to a Drive folder using rclone `sync`
#   semantics: skip identical files, upload changed, delete removed (true mirror).
#   Runs in the background so Bea/Codex doesn’t block. Includes locking, safety rails, and logging.
#
# Key features:
#   - Foreground or background execution (foreground when INVOKED_AS_CHILD=1)
#   - Locking via flock to prevent overlapping runs
#   - Honors .gitignore via `git ls-files -co --exclude-standard` (+ .codexignore if present)
#   - Optional .rcloneignore (rclone filter-style) for extra excludes beyond Git
#   - True mirror: `rclone sync` + `--delete-excluded`
#   - Optional checksum mode (RCLONE_USE_CHECKSUM=1) to avoid false uploads on mtime drift
#   - Rename detection (`--track-renames`) to minimize delete+reupload churn
#   - Deletion guard with threshold (abort on suspiciously large deletes unless FORCE=1)
#   - Remote root marker guard to prevent syncing to the wrong destination
#   - Writes `.last_sync` timestamp to remote after success
#
# Usage:
#   ./scripts/sync_to_drive.sh                 # backgrounded sync job (default)
#   INVOKED_AS_CHILD=1 ./scripts/sync_to_drive.sh    # run in foreground (watch output)
#   DRYRUN=1 ./scripts/sync_to_drive.sh        # dry-run (no changes)
#   FORCE=1  ./scripts/sync_to_drive.sh        # bypass deletion guard threshold
#
# Env vars (override as needed):
#   RCLONE_REMOTE=dcgoogledrive
#   RCLONE_REMOTE_DIR=glideclubs_context/glideclubs
#   DRIVE_USE_TRASH=false            # if "false", deletes are hard deletes (recommended for mirrors)
#   MAX_DELETES=1000                 # abort if planned deletes > MAX_DELETES (unless FORCE=1)
#   RCLONE_TRANSFERS=8               # concurrent uploaders
#   RCLONE_CHECKERS=16               # concurrent checkers
#   RCLONE_CHUNK_SIZE=64M            # upload chunk size
#   RCLONE_TPSLIMIT=0                # >0 to throttle API calls
#   RCLONE_PACER_MIN_SLEEP=10ms
#   RCLONE_PACER_MAX_SLEEP=10s
#   RCLONE_PACER_BURST=200
#   RCLONE_LOG_LEVEL=INFO            # NOTICE, INFO, DEBUG...
#   RCLONE_LOG_FORMAT=date,time,level
#   RCLONE_PROGRESS=0                # set to 1 to emit --progress updates
#   RCLONE_STATS_INTERVAL=30s        # progress cadence
#   RCLONE_STATS_ONE_LINE=0          # 1 = cleaner append-only lines
#   RCLONE_USE_CHECKSUM=1            # 1=include --checksum, 0=skip (faster first pass)
#   REQUIRE_MARKER=1                 # require marker file at remote root
#   MARKER_FILE=.mirror_root         # marker filename at remote root
#   ALLOW_BOOTSTRAP=0                # if 1, create MARKER_FILE on first run when missing
#   SYMLINK_MODE=copy                # "copy" to dereference; "skip" to keep links (effectively ignore)
#   LOG_DIR=logs
#   RCLONE_LOG_FILE=<LOG_DIR>/rclone.rclone.log   # rclone’s own log file (defaults below)
# =================================================================================================

set -euo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"

# ---------- Config & defaults ----------
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

RCLONE_REMOTE="${RCLONE_REMOTE:-dcgoogledrive}"
RCLONE_REMOTE_DIR="${RCLONE_REMOTE_DIR:-glideclubs}"   # <- canonical target
REMOTE_PATH="${RCLONE_REMOTE}:${RCLONE_REMOTE_DIR}"

DRIVE_USE_TRASH="${DRIVE_USE_TRASH:-false}"
MAX_DELETES="${MAX_DELETES:-1000}"

RCLONE_TRANSFERS="${RCLONE_TRANSFERS:-8}"
RCLONE_CHECKERS="${RCLONE_CHECKERS:-16}"
RCLONE_CHUNK_SIZE="${RCLONE_CHUNK_SIZE:-64M}"

# Default to a gentle Drive pacing profile unless caller overrides it explicitly.
AUTO_THROTTLE_NOTE=""
if [[ -z "${RCLONE_TPSLIMIT+x}" ]]; then
  RCLONE_TPSLIMIT=4
  AUTO_THROTTLE_NOTE=" (auto)"
fi
if [[ -z "${RCLONE_PACER_MIN_SLEEP+x}" ]]; then
  RCLONE_PACER_MIN_SLEEP=200ms
fi
if [[ -z "${RCLONE_PACER_BURST+x}" ]]; then
  RCLONE_PACER_BURST=4
fi
RCLONE_PACER_MAX_SLEEP="${RCLONE_PACER_MAX_SLEEP:-10s}"
RCLONE_LOG_LEVEL="${RCLONE_LOG_LEVEL:-INFO}"
RCLONE_LOG_FORMAT="${RCLONE_LOG_FORMAT:-date,time,level}"
RCLONE_PROGRESS="${RCLONE_PROGRESS:-0}"
RCLONE_STATS_INTERVAL="${RCLONE_STATS_INTERVAL:-30s}"
RCLONE_STATS_ONE_LINE="${RCLONE_STATS_ONE_LINE:-0}"
RCLONE_USE_CHECKSUM="${RCLONE_USE_CHECKSUM:-1}"

REQUIRE_MARKER="${REQUIRE_MARKER:-1}"
MARKER_FILE="${MARKER_FILE:-.mirror_root}"
ALLOW_BOOTSTRAP="${ALLOW_BOOTSTRAP:-0}"

SYMLINK_MODE="${SYMLINK_MODE:-copy}"  # "copy" to dereference; "skip" to keep links
LOG_DIR="${LOG_DIR:-logs}"
mkdir -p "$LOG_DIR" ".contract"

LOCKFILE="$REPO_ROOT/.contract/sync_to_drive.lock"
LOG_FILE="$REPO_ROOT/$LOG_DIR/rclone_sync.log"
RCLONE_LOG_FILE="${RCLONE_LOG_FILE:-$REPO_ROOT/$LOG_DIR/rclone.rclone.log}"
DRYRUN="${DRYRUN:-0}"
FORCE="${FORCE:-0}"

# ---------- Binaries check ----------
need_bin() { command -v "$1" >/dev/null 2>&1 || { echo "❌ Missing required tool: $1"; exit 1; }; }
need_bin rclone
need_bin git
if ! command -v flock >/dev/null 2>&1; then
  echo "⚠️  'flock' not found; proceeding without concurrency lock (install 'util-linux' for locking)."
fi

# ---------- Helpers ----------
ts_utc() { date -u +"%Y-%m-%d %H:%M:%S UTC"; }

# Build rclone args (shared)
build_rclone_args() {
  local -n _arr=$1
  _arr=(
    --fast-list
    --track-renames
    --delete-excluded
    --create-empty-src-dirs
    --stats "$RCLONE_STATS_INTERVAL"
    --stats-file-name-length 0
    --transfers "$RCLONE_TRANSFERS"
    --checkers "$RCLONE_CHECKERS"
    --drive-chunk-size "$RCLONE_CHUNK_SIZE"
    --drive-pacer-min-sleep "$RCLONE_PACER_MIN_SLEEP"
    --drive-pacer-burst "$RCLONE_PACER_BURST"
    --log-level "$RCLONE_LOG_LEVEL"
    --log-file "$RCLONE_LOG_FILE"
    --max-delete "$MAX_DELETES"
  )

  # Optional one-line stats
  if [[ "$RCLONE_STATS_ONE_LINE" == "1" ]]; then
    _arr+=( --stats-one-line --stats-one-line-date )
  fi

  # Optional JSON log
  if [[ -n "$RCLONE_LOG_FORMAT" ]]; then
    _arr+=( --log-format "$RCLONE_LOG_FORMAT" )
  fi

  # Progress lines if desired
  if [[ "$RCLONE_PROGRESS" == "1" ]]; then
    _arr+=( --progress )
  fi

  # Symlink policy
  if [[ "$SYMLINK_MODE" == "copy" ]]; then
    _arr+=( --copy-links )
  else
    _arr+=( --links )
  fi

  # Optional API throttle
  if [[ -n "$RCLONE_TPSLIMIT" && "$RCLONE_TPSLIMIT" != "0" ]]; then
    _arr+=( --tpslimit "$RCLONE_TPSLIMIT" )
  fi

  # Trash vs hard-delete
  if [[ "$DRIVE_USE_TRASH" == "false" ]]; then
    _arr+=( --drive-use-trash=false )
  fi

  # Respect checksum toggle
  if [[ "$RCLONE_USE_CHECKSUM" == "1" ]]; then
    _arr+=( --checksum )
  fi
}

# Ensure remote exists & marker guard
ensure_remote_ready() {
  if ! rclone lsd "$REMOTE_PATH" >/dev/null 2>&1; then
    echo "ℹ️  Remote path '$REMOTE_PATH' doesn't exist; creating..."
    rclone mkdir "$REMOTE_PATH"
  fi

  if [[ "$REQUIRE_MARKER" == "1" ]]; then
    # Check for marker existence without noisy errors: list files at root and search
    if ! rclone lsf "$REMOTE_PATH" --files-only --format p | grep -Fxq "$MARKER_FILE"; then
      if [[ "$ALLOW_BOOTSTRAP" == "1" ]]; then
        echo "Initializing mirror root marker at remote: $REMOTE_PATH/$MARKER_FILE"
        printf 'This folder is a managed mirror root.\n' | rclone rcat "$REMOTE_PATH/$MARKER_FILE"
      else
        echo "❌ Marker '$REMOTE_PATH/$MARKER_FILE' not found. Set ALLOW_BOOTSTRAP=1 to create it."
        exit 1
      fi
    fi
  fi
}

# Build a combined rclone filter file from Git + .codexignore:
#  - Start with: always exclude .git/**
#  - Include exactly what Git says is part of the repo (respects .gitignore + .codexignore)
#  - Finally, exclude everything else (- **)
build_filter_file() {
  local filter_path="$1"
  : > "$filter_path"

  # Ask Git for the authoritative file list first (respects .gitignore + .codexignore)
  local git_list
  git_list="$(mktemp)"
  git -c core.quotepath=false \
      -c core.excludesFile="$REPO_ROOT/.codexignore" \
      ls-files -co --exclude-standard -z > "$git_list"

  # Include what Git considers source-of-truth
  tr '\0' '\n' < "$git_list" | sed '/^$/d' | while IFS= read -r p; do
    printf '+ %s\n' "$p" >> "$filter_path"
  done

  # Optional: apply user-provided rclone filters from .rcloneignore so they can override Git includes.
  if [[ -f "$REPO_ROOT/.rcloneignore" ]]; then
    while IFS= read -r raw || [[ -n "$raw" ]]; do
      # trim leading/trailing whitespace (portable)
      line="${raw%%[$'\r\n']*}"
      line="$(printf '%s' "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
      [[ -z "$line" || "$line" =~ ^# ]] && continue
      if [[ "$line" =~ ^[+-] ]]; then
        # normalize to "+ <pat>" or "- <pat>"
        sign="${line:0:1}"
        rest="${line:1}"
        rest="$(printf '%s' "$rest" | sed -e 's/^[[:space:]]*//')"
        printf '%s %s\n' "$sign" "$rest" >> "$filter_path"
      else
        printf -- '- %s\n' "$line" >> "$filter_path"
      fi
    done < "$REPO_ROOT/.rcloneignore"
  fi

  # Enforce exclusions for metadata and control files
  echo "- .git/**" >> "$filter_path"
  echo "- .contract/**" >> "$filter_path"
  echo "- .gitignore" >> "$filter_path"
  echo "- .codexignore" >> "$filter_path"
  echo "- .rcloneignore" >> "$filter_path"

  # Finally, exclude everything not explicitly included
  echo "- **" >> "$filter_path"

  rm -f "$git_list"
}

# Estimate deletes via dry-run and abort if above threshold (unless FORCE=1)
deletion_guard() {
  local tmpout="$1"; shift
  if ! rclone sync "$@" --dry-run >"$tmpout" 2>&1; then
    local failure_copy="$LOG_DIR/dryrun_failure_$(date -u +"%Y%m%dT%H%M%SZ").log"
    cp "$tmpout" "$failure_copy" 2>/dev/null || failure_copy="$tmpout"
    echo "❌ Dry-run failed; details: $failure_copy"
    if command -v tail >/dev/null 2>&1; then
      echo "┬─ last dry-run lines ─────────────────────────────────────────"
      tail -n 20 "$failure_copy" || true
      echo "┴──────────────────────────────────────────────────────────────"
    fi
    if [[ ! -s "$failure_copy" ]]; then
      echo "ℹ️  No inline dry-run output captured. Check $RCLONE_LOG_FILE for rclone logs."
    fi
    return 1
  fi
  local dels
  dels="$(grep -Ei 'delet|Deleting|deleted' "$tmpout" | wc -l | tr -d ' ')"
  dels="${dels:-0}"
  if (( dels > MAX_DELETES )) && [[ "$FORCE" != "1" ]]; then
    echo "🛑 Planned deletes = $dels exceed MAX_DELETES=$MAX_DELETES. Set FORCE=1 to proceed."
    echo "See dry-run log: $tmpout"
    return 2
  fi
  return 0
}

# Child process: holds the lock for the entire sync
run_child() {
  if command -v flock >/dev/null 2>&1; then
    exec 200>"$LOCKFILE"
    if ! flock -n 200; then
      echo "⏭️  Another sync is already running. Skipping."
      exit 0
    fi
  fi

  local start_ts end_ts
  start_ts="$(ts_utc)"
  echo ""
  echo "──────────────────────────────────────────────────────────────────────────────"
  echo "🚀 rclone sync start: $start_ts   (repo: $REPO_ROOT → remote: $REMOTE_PATH)"
  echo "──────────────────────────────────────────────────────────────────────────────"

  ensure_remote_ready

  # Build filter file
  TMP_FILTER="$(mktemp)"
  TMP_DRYRUN="$(mktemp)"
  trap 'rm -f "$TMP_FILTER" "$TMP_DRYRUN"' EXIT
  build_filter_file "$TMP_FILTER"

  # Assemble rclone args
  build_rclone_args RARGS
  RARGS+=( --filter-from "$TMP_FILTER" )
  if [[ "${RCLONE_TPSLIMIT:-0}" != "0" ]]; then
    echo "⏱️  Drive API throttle$AUTO_THROTTLE_NOTE → --tpslimit=$RCLONE_TPSLIMIT, --drive-pacer-min-sleep=$RCLONE_PACER_MIN_SLEEP, --drive-pacer-burst=$RCLONE_PACER_BURST"
  fi

  echo "🔍 Scanning source & remote… (checksum: ${RCLONE_USE_CHECKSUM})"
  echo "rclone: $(rclone version | head -n1)"

  if [[ "$DRYRUN" == "1" ]]; then
    echo "🔎 DRY-RUN ONLY — no remote changes will be made."
    if ! rclone sync "$REPO_ROOT" "$REMOTE_PATH" "${RARGS[@]}" --dry-run; then
      echo "❌ rclone dry-run failed."
      exit 1
    fi
    echo "✅ DRY-RUN completed."
    exit 0
  fi

  # Deletion guard (dry-run to estimate deletes)
  if ! deletion_guard "$TMP_DRYRUN" "$REPO_ROOT" "$REMOTE_PATH" "${RARGS[@]}"; then
    exit 2
  fi

  # Real sync
  if ! rclone sync "$REPO_ROOT" "$REMOTE_PATH" "${RARGS[@]}"; then
    echo "❌ rclone sync failed."
    exit 1
  fi

  # Post-success: write last sync & re-assert marker so delete-excluded can’t remove it
  local LAST_SYNC_TS
  LAST_SYNC_TS="$(ts_utc)"
  printf '%s\n' "$LAST_SYNC_TS" | rclone rcat "${REMOTE_PATH}/.last_sync"
  printf 'This folder is a managed mirror root.\n' | rclone rcat "${REMOTE_PATH}/${MARKER_FILE}"

  end_ts="$(ts_utc)"
  echo "✅ rclone sync complete: $end_ts (started: $start_ts)"
}

# ---------- Parent: spawn background child with nohup ----------
set -euo pipefail
if [[ "${INVOKED_AS_CHILD:-0}" == "1" ]]; then
  run_child
  exit $?
fi

echo "🧳 Launching background Drive sync → ${REMOTE_PATH}"
nohup env INVOKED_AS_CHILD=1 \
         RCLONE_REMOTE="$RCLONE_REMOTE" \
         RCLONE_REMOTE_DIR="$RCLONE_REMOTE_DIR" \
         DRIVE_USE_TRASH="$DRIVE_USE_TRASH" \
         MAX_DELETES="$MAX_DELETES" \
         RCLONE_TRANSFERS="$RCLONE_TRANSFERS" \
         RCLONE_CHECKERS="$RCLONE_CHECKERS" \
         RCLONE_CHUNK_SIZE="$RCLONE_CHUNK_SIZE" \
         RCLONE_TPSLIMIT="$RCLONE_TPSLIMIT" \
         RCLONE_PACER_MIN_SLEEP="$RCLONE_PACER_MIN_SLEEP" \
         RCLONE_PACER_BURST="$RCLONE_PACER_BURST" \
         RCLONE_LOG_LEVEL="$RCLONE_LOG_LEVEL" \
         RCLONE_LOG_FORMAT="$RCLONE_LOG_FORMAT" \
         RCLONE_PROGRESS="$RCLONE_PROGRESS" \
         RCLONE_STATS_INTERVAL="$RCLONE_STATS_INTERVAL" \
         RCLONE_STATS_ONE_LINE="$RCLONE_STATS_ONE_LINE" \
         RCLONE_USE_CHECKSUM="$RCLONE_USE_CHECKSUM" \
         REQUIRE_MARKER="$REQUIRE_MARKER" \
         MARKER_FILE="$MARKER_FILE" \
         ALLOW_BOOTSTRAP="$ALLOW_BOOTSTRAP" \
         SYMLINK_MODE="$SYMLINK_MODE" \
         DRYRUN="$DRYRUN" \
         FORCE="$FORCE" \
         LOG_DIR="$LOG_DIR" \
         RCLONE_LOG_FILE="$RCLONE_LOG_FILE" \
         "$SCRIPT_PATH" >> "$LOG_FILE" 2>&1 &

BG_PID=$!
disown "$BG_PID" 2>/dev/null || true
echo "🟢 Sync running in background (pid: $BG_PID). Logs → $LOG_FILE"
