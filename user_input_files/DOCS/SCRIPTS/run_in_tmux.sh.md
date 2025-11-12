# run_in_tmux.sh — Run a Command in a Named tmux Session

Path
- scripts/run_in_tmux.sh

Purpose
- Create a tmux session that runs a command with timeout and structured logging under `/tmp/codex-work/<session>/`.

Usage
- `scripts/run_in_tmux.sh -s <session> -T 10m [-C /path] [--attach] -- <command ...>`

Outputs
- `run.log` and `exit_code` files under `/tmp/codex-work/<session>/`.

Fallback
- If tmux is unavailable, runs in the foreground with `timeout`, preserving exit code.

