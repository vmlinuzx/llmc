#!/usr/bin/env bash
# run_in_tmux.sh — Run a command in a named tmux session with timeout and logging
# Usage:
#   scripts/run_in_tmux.sh -s dc-build -T 10m [-C /path/dir] [--attach] -- "your long command here"
# Behavior:
#   - Creates /tmp/codex-work/<session> with run.log and exit_code.
#   - Runs inside tmux if available; otherwise falls back to foreground with timeout + logging.
#   - Exits with the underlying command's exit code when using fallback; tmux mode detaches by default.
set -Eeuo pipefail

SESSION=""
TIMEOUT_VAL="10m"
CWD="$PWD"
ATTACH=0

while (( "$#" )); do
  case "$1" in
    -s|--session) SESSION="$2"; shift 2;;
    -T|--timeout) TIMEOUT_VAL="$2"; shift 2;;
    -C|--chdir)   CWD="$2"; shift 2;;
    -A|--attach)  ATTACH=1; shift 1;;
    --) shift; break;;
    -h|--help)
      rg '^# ' "$0" | sed 's/^# //'; exit 0;;
    *) break;;
  esac
done

if [ -z "${SESSION}" ]; then
  echo "usage: $0 -s <session> [-T 10m] [-C dir] [--attach] -- <command>" >&2
  exit 2
fi

if [ "$#" -lt 1 ]; then
  echo "error: missing command after --" >&2
  exit 2
fi

CMD_FILE_OUT=""

OUT_DIR="/tmp/codex-work/${SESSION}"
LOG_FILE="${OUT_DIR}/run.log"
RUNNER="${OUT_DIR}/run.sh"
mkdir -p "$OUT_DIR"

CMD_FILE_OUT="${OUT_DIR}/cmd.sh"
printf '%s\n' "$*" > "$CMD_FILE_OUT"
chmod +x "$CMD_FILE_OUT"

cat > "$RUNNER" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
trap 'ec=$?; echo "$ec" > "$OUT_DIR/exit_code" 2>/dev/null || true; exit "$ec"' EXIT
exec > >(tee -a "$LOG_FILE") 2>&1
echo "[$(date -Is)] cwd: $CWD"
echo "[$(date -Is)] cmd: $(cat "$CMD_FILE")"
cd "$CWD"
bash -lc "source \"$CMD_FILE\""
EOF
chmod +x "$RUNNER"

if command -v tmux >/dev/null 2>&1; then
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "tmux session '$SESSION' already exists. Attach with: tmux attach -t $SESSION" >&2
    exit 1
  fi
  tmux new-session -d -s "$SESSION" "env LOG_FILE='$LOG_FILE' OUT_DIR='$OUT_DIR' CWD='$CWD' CMD_FILE='$CMD_FILE_OUT' timeout $TIMEOUT_VAL bash '$RUNNER'"
  echo "Started in tmux session: $SESSION"
  echo "Log: $LOG_FILE"
  echo "Attach: tmux attach -t $SESSION  |  Detach: Ctrl-b d"
  if [ "$ATTACH" = "1" ]; then
    exec tmux attach -t "$SESSION"
  fi
  exit 0
else
  echo "tmux not found; running in foreground with timeout. Log: $LOG_FILE" >&2
  # Foreground fallback preserves exit code
  LOG_FILE="$LOG_FILE" OUT_DIR="$OUT_DIR" CWD="$CWD" CMD_FILE="$CMD_FILE_OUT" timeout "$TIMEOUT_VAL" bash "$RUNNER"
fi
