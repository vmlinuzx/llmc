#!/usr/bin/env bash
# autosave.sh — Commit/push, date/version tagging, and optional Drive sync.
# Usage:
#   scripts/autosave.sh [-m "message"] [--push] [--all]
# Env:
#   AUTO_SYNC_ALL=1   # sync entire repo (ignore .codexactive), still respects .codexignore
#   AUTO_TAG=true     # create/update date/version tags (default: true)
#   AUTOSAVE_LOG=path # log file (default: logs/autosave.log)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p "$ROOT/logs" 2>/dev/null || true
LOG_FILE="${AUTOSAVE_LOG:-$ROOT/logs/autosave.log}"
log() {
  local ts; ts="$(date -Is)"; printf '[%s] %s\n' "$ts" "$*" | tee -a "$LOG_FILE" >&2
}

MSG="auto: autosave $(date -Is)"
PUSH=0
SYNC_ALL=${AUTO_SYNC_ALL:-0}
AUTO_TAG=${AUTO_TAG:-true}

while (($#)); do
  case "$1" in
    -m|--message) MSG="$2"; shift 2 ;;
    --push) PUSH=1; shift ;;
    --all) SYNC_ALL=1; shift ;;
    -h|--help)
      echo "Usage: $0 [-m \"message\"] [--push] [--all]"; exit 0 ;;
    *) log "Unknown arg: $1"; exit 2 ;;
  esac
done

if ! command -v git >/dev/null 2>&1; then
  log "git not found"; exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  log "Not a git repo: $ROOT"; exit 1
fi

# Stage and commit if needed
git add -A
 
# Large-file alert: abort if any staged file exceeds threshold (default 50MB)
# Configure via env: LARGE_FILE_ALERT_MB (integer, megabytes)
LARGE_FILE_ALERT_MB=${LARGE_FILE_ALERT_MB:-50}
LARGE_FILE_ALERT_BYTES=$(( LARGE_FILE_ALERT_MB * 1024 * 1024 ))

human_size() {
  # Prints a human-readable size for a byte count
  local bytes="$1"
  if command -v numfmt >/dev/null 2>&1; then
    numfmt --to=iec --suffix=B "$bytes"
  else
    # Fallback: simple MB display with one decimal
    awk -v b="$bytes" 'BEGIN { printf "%.1fMB", b/1024/1024 }'
  fi
}

check_large_staged() {
  local threshold_bytes="$1"
  local -a offenders=()
  # NUL-delimited for safety; Added/Modified/Renamed paths only
  while IFS= read -r -d '' f; do
    # Only check regular files present in the working tree
    [ -f "$f" ] || continue
    # Use stat; fallback to wc if stat is unavailable
    local size
    if size=$(stat -c%s -- "$f" 2>/dev/null); then :; else size=$(wc -c < "$f"); fi
    if [ "$size" -ge "$threshold_bytes" ]; then
      offenders+=("$f|$size")
    fi
  done < <(git diff --cached --name-only -z --diff-filter=AMRT)

  if [ ${#offenders[@]} -gt 0 ]; then
    log "🚫 Large file(s) detected in staging area (>${LARGE_FILE_ALERT_MB}MB):"
    for entry in "${offenders[@]}"; do
      f="${entry%%|*}"; s="${entry##*|}"
      log " - $f ($(human_size "$s"))"
    done
    log "Aborting autosave. Please fix before committing:"
    log "  • Remove from staging: git reset HEAD <file>"
    log "  • Ignore patterns in .gitignore (e.g., *.deb, *.bundle, build artifacts)"
    log "  • Move large binaries outside the repo or use LFS where appropriate"
    return 2
  fi
  return 0
}

if ! check_large_staged "$LARGE_FILE_ALERT_BYTES"; then
  exit 2
fi
commit_made=0
if git diff --cached --quiet; then
  log "no changes to commit"
else
  if git commit -m "$MSG" >/dev/null 2>&1; then
    commit_made=1
    log "commit created: $(git rev-parse --short HEAD) — $MSG"
  else
    log "commit attempt failed or no staged changes"
  fi
fi

# Date/version tags (idempotent; move if HEAD changed)
if [[ "${AUTO_TAG,,}" == "true" ]]; then
  head_sha=$(git rev-parse HEAD)
  date_tag="daily-$(date -u +%Y-%m-%d)"
  ver_tag="v$(date -u +%Y.%m.%d)"
  need_update=0
  for tag in "$date_tag" "$ver_tag"; do
    if git rev-parse -q --verify "$tag" >/dev/null 2>&1; then
      tag_sha=$(git rev-parse "$tag")
      if [ "$tag_sha" != "$head_sha" ]; then need_update=1; fi
    else
      need_update=1
    fi
  done
  if [ "$need_update" -eq 1 ]; then
    git tag -a "$date_tag" -m "Autosave snapshot $(date -u -Is)" -f >/dev/null 2>&1 || true
    git tag -a "$ver_tag" -m "Autosave snapshot $(date -u -Is)" -f >/dev/null 2>&1 || true
    log "tagged HEAD as: $date_tag, $ver_tag"
  else
    log "tags up-to-date: $date_tag, $ver_tag"
  fi
fi

# Push branch and tags if requested
if [ $PUSH -eq 1 ]; then
  if git remote | rg -q '^origin$'; then
    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)
    git push origin "$branch" >/dev/null 2>&1 || log "push failed (branch)"
    if [[ "${AUTO_TAG,,}" == "true" ]]; then
      if git rev-parse -q --verify "$date_tag" >/dev/null 2>&1; then
        git push origin "$date_tag" >/dev/null 2>&1 || true
      fi
      if git rev-parse -q --verify "$ver_tag" >/dev/null 2>&1; then
        git push origin "$ver_tag" >/dev/null 2>&1 || true
      fi
    fi
    log "pushed ${commit_made:+branch and }tags to origin/$branch"
  else
    log "no origin remote; skipped push"
  fi
fi

# Launch Drive sync (background)
if [ -f "$ROOT/scripts/sync_to_drive.sh" ]; then
  SYNC_ALL=$SYNC_ALL "$ROOT/scripts/sync_to_drive.sh" >/dev/null 2>&1 &
  log "drive sync launched (all=$SYNC_ALL)"
fi

log "autosave completed"
