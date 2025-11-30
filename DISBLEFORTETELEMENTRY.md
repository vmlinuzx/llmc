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
# CONTRACTS.md – Tool Envelope (TE) & Desktop Commander Contract Block

> Drop this into `CONTRACTS.md` near the tools / MCP section (e.g. after “Localhost / MCP Notes”).  
> Adjust heading numbers as needed. This text assumes the rest of CONTRACTS already defines repo root, roles, and test policy.

---

## X. Tool Envelope (TE) Telemetry Contract

This repo ships with a **Tool Envelope (TE)** wrapper and telemetry system:

- Wrapper script: `./scripts/te`
- Analyzer: `./scripts/te-analyze`
- Telemetry store: `.llmc/te_telemetry.db` (local SQLite, no network exfil)

TE is the default way **agents** should run shell commands while working in this repo.

### X.1 When TE MUST be used

Agents (Claude Desktop Commander, Codex, CLI tools, etc.) **MUST** run shell commands through TE when:

- Touching this repo’s code (lint, tests, RAG CLI, formatting, refactors).
- Doing file-level inspection at scale (`grep`, `find`, `rg`, etc.).
- Running LLMC/RAG utilities under `scripts/` or `tools/`.
- Performing any work that Dave expects to see in TE analytics.

Allowed pattern (Claude DC example):

```bash
cd /home/vmlinux/src/llmc   && export TE_AGENT_ID="claude-dc"   && ./scripts/te <command> [args...]
```

### X.2 TE_AGENT_ID rules

- `TE_AGENT_ID` **must** be set for all agent calls.
- Use a short, stable slug per orchestrator:
  - `claude-dc`   – Claude Desktop Commander
  - `codex-cli`   – Codex / VSCode / CLI agent
  - `minimax-cli` – Minimax CLI agent
  - `manual-dave` – reserved for Dave’s own TE runs (when he wants activity in the dashboards)

If `TE_AGENT_ID` is missing, TE will still run but telemetry will be anonymous; agents should treat that as a bug and fix it on the next command.

### X.3 Bypassing TE

Bypassing TE is **exception-only** behavior.

Agents may bypass TE **only if all of the following are true**:

1. `./scripts/te` is clearly broken or missing, **and**
2. The agent has reported a `BLOCKED_BY_TE` condition in its response, **and**
3. Dave explicitly authorizes a temporary bypass (e.g. “it’s fine to run that one without TE”).

Bypass options:

- `./scripts/te -i <command> ...` → raw pass-through, recorded minimally.
- Direct shell command (no TE) → only after explicit approval **and** with a note in the response explaining that TE was bypassed.

### X.4 RAG + TE integration

For code understanding and navigation, agents should:

- Prefer RAG-based tools **over** naive, full-file reads.
- Invoke RAG through TE so we get telemetry:

```bash
# Semantic search
./scripts/te python3 -m tools.rag.cli search "JWT validation logic" --limit 5 --json

# Retrieval plan
./scripts/te python3 -m tools.rag.cli plan "How does the authentication middleware work?"

# Freshness-aware navigation
./scripts/te python3 -m tools.rag.cli nav search "schema enrichment" /home/vmlinux/src/llmc
```

Full-file reads are allowed **only** when:

- RAG fails to surface what’s needed, or
- Dave explicitly asks for a full-file review.

In both cases, agents should mention in their response that they had to fall back to direct file reads.

### X.5 Desktop Commander specifics

When the orchestrator is **Claude Desktop Commander**:

- Treat `/home/vmlinux/src/llmc` as the canonical repo root unless Dave says otherwise.
- All shell commands the tool executes **inside this repo** should follow the TE pattern with `TE_AGENT_ID="claude-dc"`.
- Desktop Commander may:
  - Use TE for RAG calls, tests, and exploratory commands.
  - Use TE’s `grep`/`cat` enrichment for quick code peeks instead of reading entire large files directly.
- Long-lived daemons / tmux sessions:
  - Respect any tmux/job policies already in CONTRACTS.
  - Prefer single-shot TE commands over spawning new long-running background processes unless Dave explicitly requests a service.

If Desktop Commander cannot reach `./scripts/te` (pathing, permissions, etc.), it must report the problem instead of silently ignoring TE.

### X.6 Analytics & privacy notes

- TE telemetry is **local-only** by default and stored in `.llmc/te_telemetry.db`.
- It captures **command, timing, and high-level metadata**, not full code contents.
- The analytics TUI (if running) may visualize this, but it does not change the behavior contract above.

The goal is to **dogfood TE in real workflows** so Dave can see how agents actually interact with the repo.



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
