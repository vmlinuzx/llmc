#!/usr/bin/env bash
# sync_to_drive.sh (template) - Sync to Google Drive using .codexignore
set -euo pipefail

DRIVE_BASE="/mnt/g/My Drive"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="$(basename "$REPO_ROOT")"
DRIVE_FOLDER="$DRIVE_BASE/$PROJECT_NAME"

VERBOSE=0
DRY_RUN=0
FOREGROUND=0 # default background if no options

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  -v, --verbose   Print detailed progress and rsync output
  -n, --dry-run   Show what would change without writing
  -h, --help      Show this help message

Syncs repository (respecting .codexignore) to: "$DRIVE_FOLDER"
Notes:
  - With no options, runs silently in the background
  - If .codexactive exists, ONLY paths listed there are synced (whitelist). Otherwise .codexignore is used (blacklist).
EOF
}

ORIG_ARGC=$#
while (($#)); do
  case "$1" in
    -v|--verbose) VERBOSE=1; shift ;;
    -n|--dry-run) DRY_RUN=1; shift ;;
    --foreground) FOREGROUND=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

if [ $ORIG_ARGC -eq 0 ] && [ $FOREGROUND -eq 0 ]; then
  nohup "$0" --foreground >/dev/null 2>&1 &
  exit 0
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync not found. Install with: sudo apt-get install rsync" >&2
  exit 1
fi

cd "$REPO_ROOT"

INCLUDE_MODE=0
if [ -f .codexactive ]; then
  INCLUDE_MODE=1
  INCLUDE_FROM="--include-from=.codexactive"
else
  if [ ! -f .codexignore ]; then
    [ $VERBOSE -eq 1 ] && echo "Warning: .codexignore not found, syncing defaults only" >&2
    EXCLUDE_FROM=""
  else
    EXCLUDE_FROM="--exclude-from=.codexignore"
  fi
fi

mkdir -p "$DRIVE_FOLDER"

RSYNC_OPTS=( -rl --ignore-times --size-only )
if [ "$INCLUDE_MODE" -eq 1 ]; then
  RSYNC_OPTS+=( --include='*/' --exclude='.git/' )
  RSYNC_OPTS+=( "$INCLUDE_FROM" --exclude='*' )
else
  RSYNC_OPTS+=( --exclude='.git/' )
  [ -n "${EXCLUDE_FROM:-}" ] && RSYNC_OPTS+=( "$EXCLUDE_FROM" )
fi
[ $VERBOSE -eq 1 ] && RSYNC_OPTS+=( -v )
[ $DRY_RUN -eq 1 ] && RSYNC_OPTS+=( -n )

if [ $VERBOSE -eq 1 ]; then
  echo "📤 Syncing to Google Drive..."
  echo "  From: $REPO_ROOT/"
  echo "  To:   $DRIVE_FOLDER/"
  if [ "$INCLUDE_MODE" -eq 1 ]; then
    echo "  Using whitelist from: .codexactive"
  else
    [ -n "${EXCLUDE_FROM:-}" ] && echo "  Using excludes from: .codexignore"
  fi
  echo "  rsync options: ${RSYNC_OPTS[*]}"
fi

if [ $VERBOSE -eq 1 ]; then
  rsync "${RSYNC_OPTS[@]}" "$REPO_ROOT/" "$DRIVE_FOLDER/" || true
else
  rsync "${RSYNC_OPTS[@]}" "$REPO_ROOT/" "$DRIVE_FOLDER/" 2>&1 | grep -v "failed to set times" || true
fi

if [ $DRY_RUN -eq 0 ]; then
  echo "$(date -u +"%Y-%m-%d %H:%M:%S UTC")" > "$DRIVE_FOLDER/.last_sync"
  [ $VERBOSE -eq 1 ] && echo "✅ Wrote timestamp: $DRIVE_FOLDER/.last_sync"
else
  [ $VERBOSE -eq 1 ] && echo "(dry-run) Skipped timestamp write"
fi

[ $VERBOSE -eq 1 ] && echo "Done."
exit 0
