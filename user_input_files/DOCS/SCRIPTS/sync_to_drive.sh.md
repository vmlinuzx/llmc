# sync_to_drive.sh — Rclone Mirror with Safety Rails

Path
- scripts/sync_to_drive.sh

Purpose
- Background, locked, idempotent mirror of the repo to a Google Drive remote using `rclone sync`, honoring `.gitignore` and optional `.rcloneignore`.

Usage
- Foreground: `INVOKED_AS_CHILD=1 scripts/sync_to_drive.sh`
- Background (default): `scripts/sync_to_drive.sh`
- Dry run: `DRYRUN=1 scripts/sync_to_drive.sh`
- Force deletes: `FORCE=1 scripts/sync_to_drive.sh`

Important env (subset)
- `RCLONE_REMOTE`, `RCLONE_REMOTE_DIR`, `MAX_DELETES`, `REQUIRE_MARKER`, `MARKER_FILE`, `RCLONE_USE_CHECKSUM`, `RCLONE_*` tuning, `LOG_DIR`

Outputs
- Logs and guard messages to stdout/stderr; writes a `.last_sync` marker on remote after success.

