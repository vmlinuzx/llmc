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

## 3. Policies

### installs
- **rule:** No package installs without explicit approval from Dave.
- **sev:** 3

### testing
- **rule:** Follow **AGENTS.md Testing Protocol** unless change is docs-only or config-only.
- **sev:** 2


### repo_structure
- **rules:** 
  - All scripts must live in `./scripts` directory. Never place scripts or files in repo root without explicit approval.
  - No random crap in repo root. Scratch scripts go in `./.trash/`.
  - docs go in `./DOCS/`.


---


