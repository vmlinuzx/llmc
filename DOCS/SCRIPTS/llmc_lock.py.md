# llmc_lock.py — Simple File Lock Utility

Path
- scripts/llmc_lock.py

Purpose
- Provide a minimal JSON‑speaking lock service (`acquire`, `release`, `ls`) under `.llmc/locks/` for coordinating background jobs.

Usage
- Acquire: `python3 scripts/llmc_lock.py acquire --resource R --task-id T --ttl 300s [--started-at ISO]`
- Release: `python3 scripts/llmc_lock.py release --resource R --task-id T`
- List: `python3 scripts/llmc_lock.py ls`

Outputs
- JSON objects indicating lock status and ownership.

