CONTEXT CONTRACT
- **Environment:** Linux. Canonical repo = `/home/$USER/src/llmc`
- **Ingest:** read `AGENTS.md` first (operational rules), then this file (environment/policies). `AGENTS.md` is the operative doc for agents.
- **Write:** follow instructions in `AGENTS.md`; avoid editing outside requested sections.
- **If `AGENTS.md` is missing:** report `BLOCKED` and stop (no other edits).
- **If required markers referenced here aren’t found in `AGENTS.md`:** report `BLOCKED` and ask Dave for approval to add them. **Do not** add them automatically.
- **Log:** attempt to call agent-memory to record a project memory (file path + short summary). If unavailable, emit a local log line instead; never fail the run due to logging.
- **Output:** return a unified diff of the target file(s) and the memory ID. Do not propose moving paths or using `/mnt/c`.
- **Time:** use UTC format `YYYY-MM-DDTHH:MM:SSZ`.

---

## 1. Roles

### dave
- **sc:** Product owner providing directives and approvals.
- **cap:** approve plans, supply environment context, authorize escalations.
- **lim:** delegates execution to agents; no direct repository edits through this contract.

---

## 2. Tools
All operational tools (CLI inventory, MCP servers, and callable LLM helpers) are defined in `.codex/tools.json`. Reference that manifest for canonical schemas and availability; this contract only records the pointer.

### contracts_sidecar_refresh
- **steps:** run `contracts_build.py`, run `contracts_validate.py`, capture sha256, commit or stash artifacts.
- **ok:** sidecar checksum matches `contracts.sidecar.sha256`.

---

## 3. Policies

### installs
- **rule:** No package installs without explicit approval from Dave.
- **sev:** 3

### testing
- **rule:** Follow **AGENTS.md Testing Protocol** unless change is docs-only or config-only.
- **sev:** 2

### tmux
- **rule:** Long-running tasks (>2 minutes) must run inside tmux per `dc-<task>` convention.
- **sev:** 1

### repo_structure
- **rule:** All scripts must live in `./scripts` directory. Never place scripts or files in repo root without explicit approval.
- **sev:** 2

---

## 4. Core Protocol
1. Read the ask. Confirm one concrete deliverable (≤ ~50 LOC or one doc section).
2. Show a 3-bullet plan. Await approval or continue if wrapper pre-approves.
3. Do it. Change at most one file unless Dave said otherwise.
4. Validate locally (quick self-check). No extra files or tooling.

---

## 5. Stop Conditions
Stop immediately when:
- (a) deliverable is done,
- (b) blocked by missing info or missing `AGENTS.md` sections,
- (c) timebox feels hit.

If blocked:
- Print a `BLOCKED` report with exact remediation
- Perform **no** writes
- Return `NOOP`
- Then print a 5-line summary + next 3 suggested steps. Do not keep going.

---

## 6. Testing Requirements
- See **AGENTS.md Testing Protocol** for full details.
- Summary:
  1. Restart affected services
  2. Test with `lynx` (pages) or `curl` (APIs)
  3. Check logs for errors
  4. Browser spot check
  5. Report results in response
- Skip testing for: docs-only changes, config updates, comments.

---

## 7. Execution Scope
- One targeted change-set per request unless Dave approves broader work.
- Ask before installs, refactors, or long tmux/daemonized jobs.
- Stay inside the repo unless told otherwise.

---

## 8. Localhost / MCP Notes
Use the MCP/tooling defined in `.codex/tools.json`. Prefer discovery (`search_tools`, `describe_tool`) over blind calls. Emit tool calls in the format your orchestrator expects.
