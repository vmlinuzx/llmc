##AGENTS.md
LLMC Agent Charter
The user is Dave
NO RANDOM CRAP IN THE REPO ROOT.  If you need a temp script for something
consider just building it in ./.trash/ 
If it belongs in the repo root per best repo practices then good.
REPO_ROOT=~/src/llmc or REPO_ROOT=/home/vmlinux/src/llmc


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

## 3. Engineering Workflow (The "Dave Protocol")

For any task deemed **Significant** (requires design, >1 file change, complex refactor, or touching core pipelines), strictly follow this structured loop:

1.  **Logic Gate:** Determine if the task is "Significant" or "Small" (just do it).
2.  **Overview:** Provide a high-level summary of the goal to ensure alignment.
3.  **Imaginative/Research Phase:** Explore creative approaches. Deep-dive into docs/code. *Do not write implementation code yet.*
4.  **HLD (High Level Design):** Define architecture, data flow, and **Test Strategy**. Get approval.
5.  **SDD (Software Design Document):** Define specific implementation details (function signatures, schemas) and **Test Cases**. Get approval.
6.  **Implementation (TDD):**
    *   Write failing tests (from SDD cases) FIRST.
    *   Write code to pass tests.
7.  **Verification:** Run tests to confirm implementation matches design.
8.  **Documentation:** Finalize docs (`ROADMAP.md`, architecture docs).

*Note: This process ensures predictable, high-quality results and prevents "cowboy coding" chaos.*

### Context Retrieval Protocol (RAG/MCP)

You are working in a repository that has a RAG (Retrieval-Augmented Generation) system with CLI tools.
Follow these rules when answering questions or editing code.

## 4. RAG-first contract

- MANDATORY Default: **use RAG tools first** for any repo/code question.
- If RAG fails (no results, tool error, or obviously irrelevant results), silently fall back to:
  - grep / ripgrep
  - AST / structural search
  - direct file reads
- Do **not** give up after a single RAG miss. Try a better query or thresholds once, then fall back.


### Choosing between `search` and `plan`

**Use `search` when:**
- You just need to *read or summarize* code, config, or docs.
- You’re answering questions like:
  - “Where is X defined / used?”
  - “What does Y do?”
- You are not yet making code changes.

Run:
```bash
python3 -m tools.rag.cli search "query"        # --limit N, --json
```

**Use `plan` when:**
- You’re about to **change** code: refactor, add a feature, or fix a bug.
- You need a list of files/spans to touch as a **work plan**.
- You want higher-confidence targets, not just raw search hits.

Run:
```bash
python3 -m tools.rag.cli plan "query"          # --limit, --min-score, --min-confidence
```

If the user asks you to “implement”, “refactor”, “fix”, or “wire up” something:
- Prefer `plan` first.
- Only skip `plan` if the user has already given exact files and locations.

### TRUST LEVEL LOGIC
RAG results with a `trust_level`:
- VERY_HIGH SCORE >= 0.80 : treat the top result as the primary source of truth. Use it directly unless there is strong evidence it is wrong.
- HIGH = 0.60 <= score < 0.80 : generally reliable. Use as primary context, but validate for security- or production-critical decisions.
- MEDIUM = 0.35 <= score < 0.60 : useful supporting context. Combine with other sources (additional RAG hits, code reads, or grep).
- LOW = score < 0.35 : do not rely on these alone. Prefer fallbacks (grep, direct reads) or a refined query.

### How to choose `--limit`

`--limit` controls how many candidates you pull back.

**For `search`:**
- Default: `--limit 25`
- Use `--limit 10` when:
  - The query names a specific function/class/module.
  - The repo is small or the user already pointed at a file.
- Use `--limit 50` when:
  - The change is cross-cutting (logging, error handling, config keys).
  - The user says “all places”, “all usages”, or “everywhere”.

**For `plan`:**
- Default: `--limit 50`
- Use `--limit 20` for small/local changes.
- Use `--limit 80–100` only when the change is large-scale and you expect many affected files
  (e.g. rename a core API, change a base class).

**Heuristic:**
- If results look thin and you know the repo is bigger → **increase** `--limit`.
- If you’re drowning in irrelevant files → **decrease** `--limit` and/or raise thresholds.

### How to choose `--min-score` (relevance threshold)

Use `--min-score` to filter noisy results by similarity score.

- Default: let the tool’s internal default apply, or start with `--min-score 0.2` for `plan`
  when the query is broad.
- Raise to `--min-score 0.3–0.4` when:
  - Many returned files are obviously irrelevant.
  - A few hits are clearly good and have much higher scores than the rest.
- Lower to `--min-score 0.1` (or remove it) when:
  - You get “no results above threshold” but you’re confident something should match.
  - You’re exploring a small/weird repo and want recall over precision.

**Heuristic:**
- If you keep opening useless files → **raise** `--min-score`.
- If you get nothing useful at all → **lower** `--min-score` or rephrase the query.

### How to choose `--min-confidence` (LLM planning confidence)

`--min-confidence` is for `plan` outputs that include an LLM-derived confidence score per item.

- Default: `--min-confidence 0.5`
- Raise to `0.7` when:
  - You only want very safe, high-signal changes (surgical fixes, sensitive code).
  - You’re modifying core infrastructure or security-critical code.
- Lower to `0.3` when:
  - You’re exploring and prefer to see more candidates (you will filter manually).
  - The repo has sparse annotations or RAG is still warming up.

**Heuristic:**
- For **production-critical** edits → stricter (`--min-confidence 0.7`).
- For **exploratory** work → looser (`0.3–0.5`) with human judgment applied.

### Recommended flows

#### Flow A – Understand before editing

1. Run `search`:
   ```bash
   python3 -m tools.rag.cli search "user problem or feature" --limit 25 --json
   ```
2. Skim top hits.
   - If many are irrelevant → re-run with `--min-score 0.3` or refine the query.
3. Once you know where the logic lives, read files/AST normally.

#### Flow B – Plan edits safely

1. Run `plan`:
   ```bash
   python3 -m tools.rag.cli plan "short description of change" --limit 50 --min-confidence 0.5
   ```
2. Inspect planned targets:
   - If most look correct → proceed to make changes.
   - If many are wrong → increase `--min-score` or `--min-confidence`, or tighten the query.
3. Only after that, start editing files.

### Index / embed / enrich usage

These are **maintenance** commands, not default moves for every task.

- `python3 -m tools.rag.cli index [--since SHA]`
  - Use when the repo changed a lot and RAG feels stale.
  - Prefer `--since` when possible to keep it cheaper.

- `python3 -m tools.rag.cli embed [--execute]`
- `python3 -m tools.rag.cli enrich [--execute]`
  - Only run with `--execute` when the user explicitly asks you to update embeddings/enrichments.
  - Otherwise, prefer read-only/inspect modes if available.

- `doctor`, `benchmark`, `analytics`, `export`:
  - Use only when the user asks to check health, performance, or export RAG data.

---

## 2. Minimal CLI cheat sheet (for humans and agents)

```bash
# Search / plan
python3 -m tools.rag.cli search "query"        # --limit N, --json
python3 -m tools.rag.cli plan "query"          # --limit, --min-score, --min-confidence

# Index lifecycle
python3 -m tools.rag.cli index [--since SHA]   # --no-export
python3 -m tools.rag.cli sync --path PATH      # or --since SHA / --stdin
python3 -m tools.rag.cli stats [--json]
python3 -m tools.rag.cli paths

# Embeddings / enrichment
python3 -m tools.rag.cli embed [--execute]     # --limit, --model, --dim
python3 -m tools.rag.cli enrich [--execute]    # --limit, --model, --cooldown

# Health / QA / export
python3 -m tools.rag.cli doctor [-v]
python3 -m tools.rag.cli benchmark [--json]
python3 -m tools.rag.cli analytics [-d DAYS]
python3 -m tools.rag.cli export -o /tmp/llmc-rag.tar.gz
```

---

## 3. Quick mental model

- **search** → “Find and read the right code/docs.”
- **plan** → “Figure out what I’m going to change, and how confident I am.”
- `--limit` → “How many candidates do I want to juggle?”
- `--min-score` → “How picky am I about relevance?”
- `--min-confidence` → “How picky am I about changing only high-confidence targets?”

If in doubt:
1. Start with `search` + moderate `--limit`.
2. For actual edits, run `plan` with default thresholds.
3. Nudge thresholds instead of blindly accepting noisy results



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

## AGENTS FILE PROMPT COMPLETION 
- Now you understand the rules!
