# Implementation SDD — LLMC Concurrency v1 (80/20)

## Goals (v1)
- **Prevent** conflicts (don’t “fix” them): branch-per-task + file-level leases.
- **Single integration gate** enforces: format → build → tests → (optional) coverage → static checks.
- **Contract-first**: extend ChangeSet with `locks`, `base_commit`, `validation_plan`, `impact`.
- **Portable & repo-agnostic**: bash/python + Git; no language-specific AST.

## Components
1) **Lock Manager (`scripts/llmc_lock.py`)**
   - File-level leases under `.llmc/locks/`.
   - TTL refresh; **wound-wait-lite**: older task “wounds” younger (flag). Cooperating wrappers observe and back off. No hard preemption.
2) **Worktree Manager (`scripts/llmc_edit.sh`)**
   - `git worktree add -B llmc/<id> .llmc/worktrees/<id> <base_commit>`
   - Apply unified diff; commit.
3) **Integration Gate (`scripts/integration_gate.sh`)**
   - Runs repo-configured commands (per-ChangeSet `validation_plan` or env): format → build → tests → static.
   - 1 auto-fix hook (optional stub `scripts/agent_fix.sh` to wire Beatrice for a single retry).
4) **Contracts/Schemas**
   - `.llmc/schemas/changeset.schema.json` (adds `locks`, `base_commit`, `validation_plan`, `impact`).
   - `.llmc/schemas/integration_event.schema.json` (logs for observability).
5) **Wiring**
   - Preferred: call `scripts/llmc_edit.sh --changeset <json>` from Beatrice after emitting a ChangeSet.
   - Optional shim in `scripts/codex_wrap.sh` to hand ChangeSets to the integrator when `LLMC_CONCURRENCY=on`.

## Flow
Planner/Editor → **ChangeSet JSON** → `llmc_edit.sh`:
1. **Acquire leases** (each path in `locks`) via `llmc_lock.py acquire` (TTL default 600s).
2. **Worktree** at `base_commit`; apply patch; commit.
3. **Integration Gate** (format → build → tests → (optional) coverage → static) with per-ChangeSet plan.
   - If fail: try `scripts/agent_fix.sh` once (optional), else escalate.
4. **Merge** fast-forward to target branch (`main` by default).
5. **Release leases**; write JSONL event.

## Config (env defaults)
```dotenv
LLMC_CONCURRENCY=on
LEASE_TTL_SECONDS=600
LOCK_BACKOFF_MS=750
LOCK_MAX_RETRIES=40
TARGET_BRANCH=main
SAFE_LANES="**/*.md,**/*.json"
```

## Non-Goals (v1)
- No symbol-level locks, no AST merge, no automatic LLM merge. (Keep these OFF.)

## Rollout (2 steps)
1. **Shadow**: run gate without merging; log metrics.
2. **Safe lanes**: auto-merge docs/format; then expand to normal tasks with non-overlapping `locks`.

## What Beatrice must emit (contract snippet)
```json
{
  "id": "CS_2025_11_05_001",
  "intent": "Fix null handling in AuthService",
  "locks": ["src/auth/AuthService.java","src/auth/AuthServiceTest.java"],
  "base_commit": "abc123def456...",
  "diff": "<unified diff here>",
  "validation_plan": {
    "format": "mvn -q -DskipTests fmt:format || true",
    "build": "mvn -q -DskipTests package",
    "tests": ["mvn -q -Dtest=AuthServiceTest test"],
    "static_checks": ["mvn -q spotbugs:check"],
    "coverage_min": 0.80
  },
  "impact": { "files_changed": 2, "symbols": ["AuthService.process()", "AuthServiceTest"] }
}
```

## Quick Start
1. **Add env vars** (or copy `.env.example`): set `LLMC_CONCURRENCY=on`.
2. **Have Beatrice output** a ChangeSet JSON (match schema), then run:
   ```bash
   scripts/llmc_edit.sh --changeset path/to/changeset.json
   ```
3. **Shadow first** (comment merge in `llmc_edit.sh` if desired), then enable merge.
