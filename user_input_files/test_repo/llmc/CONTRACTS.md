CONTEXT CONTRACT:
- Environment: Linux. Canonical repo = /home/$USER/src/llmc
- Ingest: read AGENTS.md
- Write: follow instructions in AGENTS.md; avoid editing outside requested sections.
- If AGENTS.md is missing: create a minimal scaffold and stop (no other edits).
- If required markers aren't found: add them to AGENTS.md and stop after confirming with Dave.
- Log: attempt to call agent-memory to record a project memory (file path + short summary). If unavailable, emit a local log line instead; never fail the run due to logging.
- Output: return a unified diff of AGENTS.md and the memory ID. Do not propose moving paths or using /mnt/c.
- UTC format: YYYY-MM-DDTHH:MM:SSZ

# COMPACT OPERATING CONTRACT - No Yak Mode

### dave
- sc: Product owner providing directives and approvals.
- cap: approve plans, supply environment context, authorize escalations.
- lim: Delegates execution to agents; no direct repository edits through this contract.

## Tools
All operational tools (CLI inventory, MCP servers, and callable LLM helpers) are defined in `.codex/tools.json`. Reference that manifest for canonical schemas and availability; this contract only records the pointer.

### contracts_sidecar_refresh
- steps: run contracts_build.py, run contracts_validate.py, capture sha256, commit or stash artifacts.
- ok: sidecar checksum matches contracts.sidecar.sha256.

## Policies
### installs
- rule: No package installs without explicit approval from Dave.
- sev: 3
### testing
- rule: Follow AGENTS.md testing protocol unless change is docs-only or config-only.
- sev: 2
### tmux
- rule: Long-running tasks (>2 minutes) must run inside tmux per dc-<task> convention.
- sev: 1

## Core Protocol
- **Execution scope:** One targeted change-set per request unless Dave approves broader work.
- **Validation:** Prefer repo-native tests or lightweight scripts; document what was run.
- **Escalation:** Ask before installs, refactors, or long tmux/daemonized jobs.

## Runtime Shortcuts
- Retrieval tooling, MCP servers, and CLI requirements are enumerated in `.codex/tools.json`.

## Reference Index
- **Tool usage & smoke playbooks:** `DOCS/Local_Development_Tooling.md`
- **Full orchestration/hand-off notes:** `DOCS/Claude_Orchestration_Playbook.md`
- **Retrieval/indexing internals:** `DOCS/SDD_Contracts_Sidecar_v1.md`, `llmc/tools/rag/README.md`

## Glossary
### contracts_sidecar
- term: contracts_sidecar
- canon: contracts.min.json
- aka: sidecar, compact_contracts
### no_yak_mode
- term: no_yak_mode
- canon: compact operating contract workflow
- aka: compact_flow

Context
- Repo: /home/$USER/src/llmc. Stay in repo.
- Default model behavior: minimalist, deterministic, no network, no installs.

Task Protocol
1) Read my ask. Confirm one concrete deliverable (<= ~50 LOC or one doc section).
2) Show a 3-bullet plan. Await my approval or continue if I say 'go' (or wrapper pre-approves).
3) Do it. Change at most one file unless I said otherwise.
4) Validate locally (quick self-check). No extra files or tooling.

Stop Conditions
- Stop immediately when: (a) deliverable is done, (b) blocked by missing info, or (c) timebox feels hit.
- If blocked (missing file/markers), print a BLOCKED report with the exact remediation step, perform no writes, and return NOOP.
- Then print a 5-line summary + next 3 suggested steps. Do not keep going.

Constraints
- Ask before package installs, services, CI, docker, MCP, or scripts.
- Ask before any refactors with prepended WARNING REFACTOR REQUEST. TYPE "ENGAGE" TO CONFIRM, and only do refactor when ENGAGE is typed or selected; otherwise assume no refactors. No renames. No reorganizing. Touch only the target file.
- Be diff-aware: if content is identical, don't write.

Tooling & Install Policy (to avoid multi‑hour installs)
- Default: no network installs. If `ask_for_approval = "never"`, do not install or download anything; only report missing tools and provide copy‑paste commands.
- Timebox: if user explicitly asks to install, hard‑limit any install session to 10 minutes wall clock; stop and report partial results at the limit.
- Scope: only the following tools are allowed to be installed when requested: `node`, `npm`, `jq`, `rg`, `ollama`, `docker`, `psql`, `supabase`, `lynx`, `gh`.
- Fallbacks: when a tool is missing, use these fallbacks instead of installing:
  - supabase → use `psql` for DB tasks; skip project‑scaffold features.
  - lynx → use `curl` for HTTP checks.
  - ollama/LLM → skip; never pull models automatically.
- Vendor path: prefer repo‑local `llmc/tools/bin/*` over system PATH (user set `PATH=./tools/bin:$PATH`). Binaries in `llmc/tools/bin` must be pinned + checksummed; no silent updates.
- Budget prompts: agent must print what it intends to install, size and time estimates, and wait unless user said "go" in this session.
- CI/devcontainer: recommend using prebuilt image with pinned CLIs; agent must prefer that when present.

Operational Guardrails
- Never apt-get/apt install without explicit user opt‑in.
- Never run install loops or retries silently; max 1 retry per tool.
- Abort any install that exceeds 2 minutes without progress output.

tmux Policy (long-running tasks)
- Any task expected to exceed 2 minutes MUST run inside a named tmux session: `dc-<task>` (e.g., `dc-build`, `dc-tests`, `dc-install`).
- Wrap long tasks with `timeout` and tee logs to `/tmp/codex-work/<session>/run.log`.
- Clean up: detach and kill the tmux session when finished; do not leave background processes.
- No daemonizing inside tmux without explicit approval.
- Example:
  - `mkdir -p /tmp/codex-work/dc-install`
  - `tmux new -s dc-install 'timeout 10m bash -lc "YOUR_CMD |& tee /tmp/codex-work/dc-install/run.log"'`
  - `# Reattach: tmux attach -t dc-install  |  Detach: Ctrl-b d  |  Kill: tmux kill-session -t dc-install`
 - Helper: `llmc/scripts/run_in_tmux.sh -s dc-install -T 10m -- "YOUR_CMD"`

Optional Light Log (only if something changed)
- Update DOCS/SESSION_LATEST.md with: Updated:<UTC>, Last actions (<=3 bullets), Next (3 bullets).
- If file absent, create it. If identical, skip writing.

END SESSION
- When I type 'END SESSION': summarize in 6-10 bullets (what changed, open decisions, next).
- No file writes unless I explicitly say 'write docs'.


## Testing Requirements

See AGENTS.md Testing Protocol section for full details.

Summary:
1. Restart affected services
2. Test with lynx (pages) or curl (APIs)
3. Check logs for errors
4. Browser spot check
5. Report results in response

Skip testing for: Docs-only changes, config updates, comments.





### File Encoding

All repository files must be UTF-8 (no BOM) with LF line endings.


## Localhost Tooling Reference
Operational tooling inventories and usage patterns are detailed in `DOCS/Local_Development_Tooling.md`. Agents should consult that document (along with `.codex/tools.json`) for specific commands, guardrails, and smoke-test procedures.

Guardrails & Conventions (localhost)
- Idempotence: prefer commands safe to re-run.
- Dry runs first: use --dry-run/--check or present diffs before mutating.
- No credentials storage: don’t write ~/.ssh, ~/.gitconfig, or global stores.
- Paths: operate within the repo or $WORKDIR; temp files under /tmp/codex-work.
- Large ops: limit breadth (rg -M 2000, tree -L depth) to avoid heavy scans.
- Parallelism: use $(nproc) but cap to ≤ 8 unless explicitly allowed.

Containers & Compose
- Podman may be used for local experiments; prefer Podman unless Docker-specific features are required.
- Docker is available; Compose v2 only when needed and must be called out.


## MCP Tools (optional)

Desktop Commander (if configured)
- Scope: local dev automation — terminal commands, process management, file ops, diff-style editing.
- Guardrails: repo/path allow-list; dry-run diffs before edits; clean up processes; default timeout 10m; no credential exfiltration; logs to /tmp/codex-work/desktop-commander/<task>/.
- Conventions: session names dc-<task>; ripgrep-based search excluding heavy dirs.

Database Toolbox (if configured)
- Scope: standardized tools for SQL/HTTP datasets.
- Guardrails: only declared sources; read-first policy; paramize secrets via env; timeouts/logs to /tmp/codex-work/gcp-toolbox/<task>/.

gcloud CLI (local)
- Scope: read/list/describe by default; mutating actions require explicit plan + rollback + approval.
- Guardrails: project allow-list; ADC only; flag cost-impacting changes.


## MCP Resource Policy
- Prefer MCP resources/templates over ad‑hoc web search.
- Save MCP outputs to /tmp/codex-work/<server>/<task>/ and sanitize logs.
- Read-first: gather schema/info before any mutating action.
- Cost & approval: any non‑trivial cost requires explicit note and rollback/verification steps.
