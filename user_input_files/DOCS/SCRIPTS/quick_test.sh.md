# quick_test.sh — Minimal API Smoke Tests

Path
- scripts/quick_test.sh

Purpose
- Hit a few health and search endpoints on a running service and optionally `/api/me` when `GC_TOKEN` is set.

Usage
- `scripts/quick_test.sh [BASE_URL]` (default `http://localhost:3001`)

What it does
- GET `/api/healthz`, `/api/selftest`
- POST `/api/search/text` with example payload
- POST `/api/search/radius` with example payload
- GET `/api/me` with `Authorization: Bearer $GC_TOKEN` if present

