# LLMC Roadmap (Focused Items)

## 1) Repository Registration Validation (Priority: High)
- Validate path on `register`:
  - Must exist and be a directory
  - Must be readable, writable, and accessible (x) for `.rag/` and `logs/`
- Environment checks with clear messaging:
  - Git availability and repo detection (`git rev-parse`) — warn if absent; fallback to filesystem scan
  - No destructive writes during validation; checks only
- CLI support:
  - Fail fast with actionable errors on invalid paths/permissions
  - Display warnings for non-fatal conditions (non-git, limited environment)

Rationale: Prevents mis-registrations (typos, wrong paths) and surfaces likely runtime failures early.

## 2) Config-Driven Defaults
- Read `llmc.toml` for enrichment defaults (e.g., `[enrichment].batch_size`) with precedence: env > TOML > defaults
- Document logging config `[logging]` used by service for rotation behavior

## 3) Operational Quality
- `status --json` output for tooling
- Example `systemd` service/timer for daemon
- Brief runbook: start/stop, logs location, rotation behavior, troubleshooting

## 4) Log Rotation Hardening (Optional)
- Simple advisory file-lock during truncation to avoid concurrent writes
- Streaming tail for very large JSONL files (memory safety)

