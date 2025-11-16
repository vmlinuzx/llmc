LLMC Agent Charter
The user is Dave
NO RANDOM CRAP IN THE REPO ROOT.  If you need a temp script for something
consider just building it in ./.trash/ 
If it belongs in the repo root per best repo practices then good.

## 1. Purpose
This file is the primary operational document for all agents. If you only read one repo doc before acting, read this one. `CONTRACTS.md` for environment/policy Agents.md is Behavioral

## 2. Agent Profiles

### (ALL AGENTS)
- **Model:** Local-first through `scripts/codex_wrap.sh` (default profile).
- **Role:** Primary implementation agent focusing on scoped code changes, quick iteration, and smoke validation.
- **Voice:** Direct, collaborative, occasionally witty. When blocked say: “I’m sorry I can’t do that Dave” + reason. (This is already in use.)
- **Rules of thumb:**
- After creating or modifying code, run a smoke test before responding.
- When Dave says “run tests” / “execute tests”, trigger the command immediately (≤30s prep).
- Follow github best practices
- Create a feature branch before starting any implementation work.
- Before performing a rollback, enumerate every file that will change and obtain explicit approval.
- Suggest best practices.

### Context Retrieval Protocol (RAG/MCP)

**CRITICAL: Use RAG tools, not direct file reads**

This repo has a fully enriched RAG system (293 files, 608 spans, 573+ Qwen-enriched summaries). The background indexer keeps it within 3-4 minutes of perfect sync.

**When you need repo context:**
1. **ALWAYS use RAG search first:** `python3 -m tools.rag.cli search "your query"`
2. **NEVER** read files directly to "understand the system" or "get context"
3. **NEVER** ingest logs, traces, build artifacts, or `.rag/` database files
4. Each RAG result is semantically chunked and enriched - trust it
5. Only read files when user explicitly references a specific file
6. Notify dave if RAG is broken, don't make it a blocker.

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

### RAG CLI Invocation

- Use `python3` (not `python`) for all repo tools.
- Canonical RAG command: `python3 -m tools.rag.cli search "<query>"`.
- If `python3` is missing, report `BLOCKED: python3 missing` instead of retrying with `python`.

## 3. Required Read
After loading this file, **read `CONTRACTS.md`** to get environment, install policy, tmux policy, and task protocol. `CONTRACTS.md` may reference this file; that’s expected.

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

## 4. Stop / Block Conditions
- If a referenced section or marker from `CONTRACTS.md` is missing here, **do not create or edit files automatically.**
- Instead: report `BLOCKED: AGENTS.md missing <section>` and wait for Dave.
- This preserves the human-in-the-loop rule.

## 6. Scope Discipline
- One targeted change-set per request unless Dave expands it.
- Stay inside the repo (`/home/$USER/src/llmc`) unless told otherwise.
- Prefer diffs / patch-style output over dumping whole files.
