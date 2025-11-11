#!/usr/bin/env bash
set -euo pipefail

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXEC_ROOT="${LLMC_EXEC_ROOT:-$SCRIPT_ROOT}"
REPO_ROOT="${LLMC_TARGET_REPO:-$EXEC_ROOT}"
INCOMING_DIR="$REPO_ROOT/research/incoming"
ARCHIVE_DIR="$REPO_ROOT/DOCS/RESEARCH/Deep_Research"
ASSET_DIR="$ARCHIVE_DIR/assets"
LOG_FILE="$REPO_ROOT/logs/deep_research_ingest.log"

DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: scripts/deep_research_ingest.sh [--repo PATH] [--dry-run]

Moves files dropped into research/incoming/ into the long-term research archive
and triggers RAG sync for Markdown notes.
EOF
}

while (($#)); do
  case "$1" in
    --repo)
      if [ $# -lt 2 ]; then
        usage >&2
        exit 2
      fi
      REPO_ROOT="$(realpath "$2")"
      INCOMING_DIR="$REPO_ROOT/research/incoming"
      ARCHIVE_DIR="$REPO_ROOT/DOCS/RESEARCH/Deep_Research"
      ASSET_DIR="$ARCHIVE_DIR/assets"
      LOG_FILE="$REPO_ROOT/logs/deep_research_ingest.log"
      shift 2
      ;;
    --repo=*)
      REPO_ROOT="$(realpath "${1#*=}")"
      INCOMING_DIR="$REPO_ROOT/research/incoming"
      ARCHIVE_DIR="$REPO_ROOT/DOCS/RESEARCH/Deep_Research"
      ASSET_DIR="$ARCHIVE_DIR/assets"
      LOG_FILE="$REPO_ROOT/logs/deep_research_ingest.log"
      shift 1
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

export LLMC_TARGET_REPO="$REPO_ROOT"

mkdir -p "$INCOMING_DIR" "$ARCHIVE_DIR" "$ASSET_DIR" "$(dirname "$LOG_FILE")"

timestamp_utc() {
  date -u +"%Y%m%dT%H%M%SZ"
}

slugify() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

MD_TARGETS=()
PROCESSED=0

shopt -s nullglob
for path in "$INCOMING_DIR"/*; do
  name="$(basename "$path")"
  # Skip the template itself
  if [ "$name" = "deep_research_notes.template.md" ]; then
    continue
  fi
  if [ -d "$path" ]; then
    echo "Skipping directory $path (move files individually)." >&2
    continue
  fi

  ts="$(timestamp_utc)"
  ext="${name##*.}"
  base="${name%.*}"
  slug="$(slugify "$base")"
  [ -z "$slug" ] && slug="note"

  dest=""
  if [[ "$ext" =~ ^[mM][dD]$ ]]; then
    dest="$ARCHIVE_DIR/${ts}_${slug}.md"
  else
    dest="$ASSET_DIR/${ts}_${slug}.${ext}"
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    printf '[dry-run] %s -> %s\n' "$path" "$dest"
    continue
  fi

  mkdir -p "$(dirname "$dest")"
  mv "$path" "$dest"
  printf '[ingest] %s -> %s\n' "$path" "$dest"
  printf '%s\t%s\t%s\n' "$(date -Is)" "$path" "$dest" >>"$LOG_FILE"

  if [[ "$dest" == *.md ]]; then
    MD_TARGETS+=("$dest")
  fi
  PROCESSED=$((PROCESSED + 1))
done
shopt -u nullglob

if [ "$PROCESSED" -eq 0 ]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] No files to ingest."
  else
    echo "[ingest] No new files detected."
  fi
  exit 0
fi

if [ "$DRY_RUN" -eq 1 ]; then
  exit 0
fi

if [ "${#MD_TARGETS[@]}" -gt 0 ]; then
  echo "[ingest] Syncing ${#MD_TARGETS[@]} markdown note(s) into RAG index."
  "$EXEC_ROOT/scripts/rag_sync.sh" --repo "$REPO_ROOT" "${MD_TARGETS[@]}"
else
  echo "[ingest] No markdown notes found to sync."
fi

echo "[ingest] Done."
