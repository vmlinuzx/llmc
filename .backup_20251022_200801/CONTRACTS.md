COMPACT OPERATING CONTRACT - Template

Context
- Repo: this project’s root (where `template/` was copied). Stay in repo.
- Default behavior: minimalist, deterministic, no network installs unless asked.

Task Protocol
1) Confirm one concrete deliverable (≤ ~50 LOC or one doc section).
2) Show a short 3‑bullet plan. Continue if approved or wrapper pre‑approves.
3) Do it. Change at most one file unless asked otherwise.
4) Validate locally with a quick self‑check.

Stop Conditions
- Stop when (a) deliverable done, (b) blocked by missing info, or (c) timebox hit.
- If blocked: print BLOCKED with remediation, perform no writes.

Constraints
- Ask before package installs, services, CI, docker, MCP, or repo‑wide refactors.
- No renames or reorganizing unless explicitly requested.
- Be diff‑aware: skip writes if identical.

Testing Requirements
1) Restart affected services (if applicable)
2) CLI test for the change (curl/lynx/node/python/etc.)
3) Check logs for errors
4) Optional spot check

Skip testing for: docs‑only, config updates, comments.

File Encoding
- All files UTF‑8 (no BOM), LF line endings

