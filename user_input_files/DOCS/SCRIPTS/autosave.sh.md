# autosave.sh — Commit/Tag/Optional Push + Drive Sync

Path
- scripts/autosave.sh

Purpose
- Quality‑of‑life helper to stage all changes, commit with a generated or custom message, maintain date/version tags, optionally push, and kick off a background Drive sync.

Usage
- `scripts/autosave.sh [-m "message"] [--push] [--all]`

Environment
- `AUTOSAVE_LOG` (default `logs/autosave.log`)
- `AUTO_TAG=true|false` (default true)
- `AUTO_SYNC_ALL=1` mirror entire repo (still respects `.codexignore`)
- `LARGE_FILE_ALERT_MB` (default 50) — aborts if staged files exceed this size

Behavior
- Verifies a git repo; stages all; warns and aborts on staged files larger than the threshold (lists offenders). Creates/updates tags `daily-YYYY-MM-DD` and `vYYYY.MM.DD`. If `--push`, pushes branch and tags to `origin` when present. Launches `scripts/sync_to_drive.sh` in the background.

