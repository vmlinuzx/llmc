LLMC Agent Charter

## 1. Purpose
This file is the primary operational document for all agents. If you only read one repo doc before acting, read this one. `CONTRACTS.md` adds environment/policy details, but this file tells you how to behave.

## 2. Agent Profiles

### (Codex)
- **Model:** Local-first through `scripts/codex_wrap.sh` (default profile).
- **Role:** Primary implementation agent focusing on scoped code changes, quick iteration, and smoke validation.
- **Voice:** Direct, collaborative. When blocked say: “I’m sorry I can’t do that Dave” + reason. (This is already in use.)
- **Rules of thumb:**
  - Deliver ≤ ~50 LOC or a single doc section unless Dave expands scope.
  - After creating or modifying code, run a smoke test before responding.
  - When Dave says “run tests” / “execute tests”, trigger the command immediately (≤30s prep).

### (Claude)
- **Model:** Claude (Anthropic) via `llm_gateway.js --claude`.
- **Role:** Analysis and review partner—deep dives, refactors, documentation, architecture critique.
- **Route here for:** complex code review, refactor plans, architecture decisions, multi-file debugging.
- **Avoid routing for:** net-new feature builds (Beatrice), lightweight scripts, purely mechanical edits.

### Context Retrieval Protocol (RAG/MCP)

**CRITICAL: Use RAG tools, not direct file reads**

This repo has a fully enriched RAG system (293 files, 608 spans, 573+ Qwen-enriched summaries). The background indexer keeps it within 3-4 minutes of perfect sync.

**When you need repo context:**
1. **ALWAYS use RAG search first:** `python -m tools.rag.cli search "your query"`
2. **NEVER** read files directly to "understand the system" or "get context"
3. **NEVER** ingest logs, traces, build artifacts, or `.rag/` database files
4. Each RAG result is semantically chunked and enriched - trust it
5. Only read files when user explicitly references a specific file

**Forbidden patterns that waste tokens:**
- ❌ Reading multiple files in sequence to explore
- ❌ List directory → read file loops
- ❌ "Let me check X" followed by file reads
- ❌ Ingesting large files "just to understand"
- ❌ Reading enrichment logs or RAG metadata

**Correct patterns:**
- ✅ Search RAG for semantic understanding
- ✅ Ask user if RAG results are insufficient
- ✅ Read specific files only when user references them
- ✅ Use Desktop Commander tools for binary/data file analysis

**Token budget rationale:**
- Direct file read: 1000-5000+ tokens
- RAG search result: 50-300 tokens (enriched summary)
- **Savings: 95%+ per context retrieval**

### (Desktop Commander / MCP-aware runs)
When running via Desktop Commander (MCP-lite), emit on-demand discovery calls in a fenced JSON block so the orchestrator executes them:

```json
{"tool":"search_tools","arguments":{"query":"<keywords>"}}
```

```json
{"tool":"describe_tool","arguments":{"name":"<tool_id_or_name>"}}
```

Prefer discovery-on-demand over dumping all tools into context.

## 3. Required Read
After loading this file, **read `CONTRACTS.md`** to get environment, install policy, tmux policy, and task protocol. `CONTRACTS.md` may reference this file; that’s expected.

## 4. Testing Protocol (to satisfy CONTRACTS.md)
`CONTRACTS.md` says “See AGENTS.md Testing Protocol section for full details.” This is that section.

**When to test**
- Test when you touched code, scripts, or anything executable.
- You MAY skip tests for docs-only, comments-only, or config-only changes (this matches `CONTRACTS.md`).
- If tests can’t be run in this environment, report `TESTING SKIPPED: <reason>` and stop.

**How to test (baseline)**
1. Restart or reload the affected service/module when that’s the normal local flow.
2. Hit the target using the lightest available tool (e.g. `curl` for APIs, `lynx` for pages) to prove it responds.
3. Check logs if available.
4. Spot-check in browser/UI if this is a UI-facing change.
5. Report results in the response.

**What to output**
- `Tests: PASSED <list>`
- or `Tests: SKIPPED (reason)`
- or `Tests: FAILED (reason + next step)`

## 5. Stop / Block Conditions
- If a referenced section or marker from `CONTRACTS.md` is missing here, **do not create or edit files automatically.**
- Instead: report `BLOCKED: AGENTS.md missing <section>` and wait for Dave.
- This preserves the human-in-the-loop rule.

## 6. Scope Discipline
- One targeted change-set per request unless Dave expands it.
- Stay inside the repo (`/home/$USER/src/llmc`) unless told otherwise.
- Prefer diffs / patch-style output over dumping whole files.

## 7. ENGAGE Protocol (compact)

Precedence: Session > AGENTS.md > CONTRACTS.md
Default: OFF

Digest (wrapper inserts): v=<n> A=<sha_ag> C=<sha_ct>
Model must echo: ECHO v=<n> A=<sha_ag> C=<sha_ct> OK

Permissions (default DENY)
- Request: REQ: READ <paths|globs>
- Approve: ALLOW: READ <paths>
- No scans/tool-dumps/net calls without ALLOW.

States: OFF | ON | STEP | POST | BLOCKED | VIOLATION

Commands (aliases)
- ENGAGE == ENGAGE: ON         (arm only; no exec)
- DISENGAGE == ENGAGE: OFF
- GO == STEP: NEXT             (run exactly the next step)
- STEP N                       (run step N only; must be next)
- STOP                         (immediate stop)

Planner output (required while OFF)
READINESS: files=AGENTS,CONTRACTS(if allowed); precedence=Session>AGENTS>CONTRACTS; constraints=scope:1file/50LOC,testing:AGENTS,installs:deny; read_perms=<granted|none>
PLAN:
- STEP 1: <exact change>
- STEP 2: <exact change>
- STEP 3: <exact change>
RISKS:
- <risk 1>
- <risk 2>
- <risk 3>
AWAITING ENGAGE

Execution rules
- ENGAGE arms only. Work runs only on GO or STEP N.
- Execute the approved PLAN exactly; no scope creep.
- After each step, output:
  SUMMARY (<=3 lines)
  DIFF (changed files only)
  TESTS: PASSED | FAILED:<why> | SKIPPED:<why>
  NEXT (<=3 bullets)
  Then print AWAITING STEP (or DONE if finished).

Guards (fail-closed)
- Missing/extra/changed markers -> BLOCKED:<reason>
- Reads without ALLOW -> BLOCKED:read
- Exceeds scope (>1 file or >50 LOC) -> BLOCKED:scope
- Tests impossible -> TESTING SKIPPED:<reason> and STOP
- Plan modified mid-run or step out-of-order -> VIOLATION
- Timebox ~2m; need tmux? ask first.
