#!/usr/bin/env bash
set -euo pipefail
python3 scripts/contracts_build.py --in CONTRACTS.md --out contracts.min.json >/dev/null
python3 scripts/contracts_validate.py >/dev/null
