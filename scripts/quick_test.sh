#!/usr/bin/env bash
# Usage: ./scripts/quick_test.sh [BASE_URL]
# Description: Smoke checks for health/selftest and auth-me. Set GC_TOKEN to test /api/me.
# Notes: Defaults to http://localhost:3001. Idempotent and safe.
set -euo pipefail

BASE="${1:-http://localhost:3001}"

echo "[1] Healthz: $BASE/api/healthz"
curl -s "$BASE/api/healthz" | jq .

echo "[2] Selftest: $BASE/api/selftest"
curl -s "$BASE/api/selftest" | jq .

echo "[3] Text search (clubs)"
curl -s -X POST "$BASE/api/search/text" \
  -H "Content-Type: application/json" \
  -d '{"q":"High Plains","type":"clubs","limit":5}' | jq '{count: ((.clubs // []) | length), example: ((.clubs // []) | .[0]? // "n/a")}'

echo "[4] Radius search (sites near Amarillo)"
curl -s -X POST "$BASE/api/search/radius" \
  -H "Content-Type: application/json" \
  -d '{"lat":35.222,"lng":-101.831,"radiusMiles":50,"type":"sites","limit":5}' | jq '{count: ((.sites // []) | length)}'

echo "[5] Me (requires token)"
if [[ -n "${GC_TOKEN:-}" ]]; then
  curl -s "$BASE/api/me" -H "Authorization: Bearer $GC_TOKEN" | jq .
else
  echo "  Skipped (set GC_TOKEN)"
fi
