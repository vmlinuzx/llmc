# Learnings - SDD RLM Config Surface 1X

Session started: 2026-01-25T07:14:05.558Z

## Project Context
- This is the LLMC repo (Large Language Model Compressor)
- Focus: RLM (Reflective Language Model) configuration externalization
- Goal: Replace 92 hardcoded values with config-driven system
- Priority: P0 (Critical) - blocks hospital deployments

## Key Requirements
- Nested config structures (not flat)
- Hybrid validation (hard-fail critical; warn+default non-critical)
- Security policy MUST be configurable
- No environment variable overrides (config-file-only)
- TDD required

## File Inventory (from SDD Section 3)
**Core files to modify:**
- llmc/rlm/config.py (incomplete parsing/validation, uses pop())
- llmc/rlm/session.py (threads config to budget+sandbox, not nav)
- llmc/rlm/nav/treesitter_nav.py (no config, 2 callsites only)
- llmc/rlm/sandbox/process_backend.py (needs permissive mode)
- llmc/rlm/governance/budget.py (pricing partially configurable)

**Test files:**
- tests/rlm/test_config.py
- tests/rlm/test_nav.py
