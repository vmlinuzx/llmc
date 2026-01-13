[6~## AGENTS.md — LLMC Agent Charter

The user is **Dave**.

- **Repo root:** `~/src/llmc` (aka `/path/to/your/llmc/repo`)
- **Rule:** NO RANDOM CRAP IN THE REPO ROOT.  
  - If you need a scratch script, prefer `./.trash/`.
  - If it belongs in repo root by common best practice (README, pyproject, etc.), that’s fine.

---

## 1. Purpose

This file is the primary **behavioral** contract for all agents working in this repo.

- **AGENTS.md** → how to behave and work.
- **CONTRACTS.md** → environment, tooling, and policy.

If you only read one doc before acting, read **this one**, then skim **CONTRACTS.md**.

---

## 2. Agent Profile (ALL AGENTS)

### Rules of Thumb

- After changing code, run a **smoke test** before responding that the ask is successful.
- When Dave says “run tests” / “execute tests”, run the tests immediately (≤30 seconds of prep).
- Follow **GitHub best practices**:
  - Create a feature branch before non-trivial work.
  - Keep commits small and focused; prefer PR-ready patch sets.
- Before performing a rollback, enumerate every file that will change and obtain explicit approval.
- Prefer **patch-style changes** (diffs) over rewriting whole files.

### Git Safety Rules (CRITICAL)
This is a multi user multi agent repo.  If you are told to commit and there
are untracked files (and there almost always will be), stop and ask what to do. 
Generally it's fine to just commit all untracked files, it's never ok to
revert or do anything that will destroy untracked files without the word
ENGAGE from the user.

- **NEVER** run `git reset HEAD~` or `git revert HEAD` without explicit approval.
- **NEVER** delete files (via `rm`, `git rm`, or any other method) without explicit approval.
- **NEVER** assume a file is "safe to delete" - always ask first.
- If you need to undo a commit, **ask Dave** and enumerate exactly what will change.
- If you see untracked files you didn't create, **ask Dave** before touching them.

---

## 3. Engineering Workflow — “The Dave Protocol”

For any task that is **Significant**  
(>1 file, non-trivial refactor, core pipeline, or anything Dave labels “Important”):

1. **Logic Gate**
   - Decide: **Small** (just do it) vs **Significant** (follow this loop).
   - If unsure, treat it as **Significant**.

2. **Overview**
   - Briefly restate the goal in your own words to confirm alignment.

3. **Imaginative / Research Phase**
   - Explore approaches, read code, RAG, docs.
   - **Do not** write implementation code yet.
   - Call out key risks / unknowns.

4. **HLD – High Level Design**
   - Describe architecture, data flow, and **test strategy**.
   - Identify which modules / services will change.
   - Get explicit approval before proceeding.

5. **SDD – Software Design Document**
   - Specify function signatures, data contracts, and concrete **test cases**.
   - Note any migrations, config changes, or CLI impacts.
   - Get approval before coding.

6. **Implementation – TDD where practical**
   - Write failing tests from the SDD (when reasonable).
   - Implement code to make tests pass.
   - Keep changeset focused and well-diffed.

7. **Verification**
   - Run targeted tests (unit / integration / CLI) for affected areas.
   - Summarize what you ran and the results.

8. **Documentation**
   - Update or create docs as needed:
     - Roadmap entries
     - Architecture docs
     - CLI usage / examples

This loop exists to prevent “cowboy coding” and keep LLMC maintainable.

---

## 4. Context Retrieval Protocol (RAG / MCP)

The repo includes a RAG system with CLI entrypoints. Use it, but don’t worship it.

### 4.1 RAG-First Contract

- **Default:** For repo/code questions, try **RAG tools first**.
- If RAG fails (no results, tool errors, or obviously weird hits), **silently fall back** to:
  - `rg` / `grep`
  - AST / structural search
  - Direct file reads
- Don’t give up after a single RAG miss:
  - Try one improved query, then fall back.
  - Never loop endlessly tweaking thresholds.

### 4.2 What RAG Scores Mean (and Don’t)

- Similarity scores from RAG are **for ranking only**.
- They are **not calibrated confidence** and are **not percentages**.
- **Never** say “this is 80% relevant” based on a raw score.
- Treat the **ordering** of results as useful; treat the **absolute number** as noisy.

### 4.3 Dependency Analysis Protocol

When you need to understand **file dependencies** (parents/children) and RAG is insufficient:

1.  **Parent Relationships (Who imports X?):**
    - Use `search_file_content` to find imports of the target module.
    - **Pattern:** `import <module>` or `from <module> import`
    - **Scope:** Search relevant directories (e.g., `src/`, `scripts/`, `tests/`) or the whole repo if unsure.
    - **Example:** `search_file_content --pattern "from scripts.router import" --include "*.py"`

2.  **Child Relationships (Who does X import?):**
    - Use `read_file` on the target file.
    - Analyze the `import` and `from ... import` statements at the top of the file.

**Do not** rely on external enrichment tools for this unless explicitly instructed.

---

## 5. Startup Context (FIRST THING TO RUN)

**Before diving into any task**, run `mcschema` to get instant codebase orientation:

```bash
python3 -m llmc.mcschema
```

This gives you (~600 tokens):
- **Entry points:** All CLI commands and their targets
- **Modules:** Top directories by file count with purpose summaries
- **Hotspots:** Most connected files (where changes ripple)
- **Recent commits:** Last 5 commits to see what's been worked on
- **Active files:** Files modified in last 7 days (current focus areas)
- **Patterns:** Class/function/method counts, most referenced symbols

**Example output:**
```
# llmc
1021 files, 10178 spans, 5858 entities, 23541 edges

entry_points:
  - llmc-cli → llmc.main:app
  - mcgrep → llmc.mcgrep:main
  ...

hotspots: (most connected files)
  llmc/rag/service.py (433 edges)
  llmc/rag/cli.py (344 edges)
  ...

recent_commits:
  9362dbf fix(graph): create stub nodes for external refs...
  ...

patterns: method: 2968, function: 2168, class: 714
```

**Why this matters:** You now know WHERE to look before you start searching. The hotspots tell you which files are "load-bearing" (touch with care). The recent commits tell you what Dave's been working on.

---

## 6. RAG Tooling Reference



**Primary Interface:** The `mc*` CLI tools. These are thin, graph-enriched wrappers around the RAG system.

| Command | Purpose | Example |
|---------|---------|--------|
| `mcschema` | Codebase overview + recent activity (~600 tokens) | `python3 -m llmc.mcschema` |
| `mcgrep` | Semantic search + file descriptions | `python3 -m llmc.mcgrep "router"` |
| `mcwho` | Who uses/calls this symbol? | `python3 -m llmc.mcwho Database` |
| `mcinspect` | Deep symbol inspection + graph | `python3 -m llmc.mcinspect Foo` |
| `mcread` | Read file with graph context | `python3 -m llmc.mcread llmc/rag/database.py` |
| `mcrun` | Execute command with logging | `python3 -m llmc.mcrun pytest tests/` |

### 6.1 Mechanical Context Tools (LSP / Tree-Sitter)

These commands provide **surgical precision** for code navigation using the Tree-Sitter graph index.

| Command | Purpose | Example |
|---------|---------|--------|
| `skeleton` | Generate repo "header file" (signatures + docstrings, no bodies) | `python3 -m llmc.rag.cli skeleton --limit 100` |
| `nav read` | Fetch implementation code for a specific symbol | `python3 -m llmc.rag.cli nav read GraphDatabase.bulk_insert_nodes` |
| `nav where-used` | Find usage sites of a symbol | `python3 -m llmc.rag.cli nav where-used Skeletonizer` |
| `nav lineage` | Get call graph (callers/callees) | `python3 -m llmc.rag.cli nav lineage process_repo` |

**The "Instant Omniscience" Pattern:**

1. Run `skeleton --limit 100` at session start → You now know **what** exists and **where**
2. When you need to see **how** something works → `nav read <symbol>`
3. This is ~10x more token-efficient than reading entire files

**Example workflow:**
```bash
# See the whole repo structure (signatures only)
python3 -m llmc.rag.cli skeleton --limit 100

# Now you see "GraphDatabase.bulk_insert_nodes" in the skeleton...
# Fetch just that implementation (20 lines vs 400 line file)
python3 -m llmc.rag.cli nav read GraphDatabase.bulk_insert_nodes
```

### Training Data Generation

All `mc*` tools support `--emit-training` to generate OpenAI-format tool calling examples:

```bash
python3 -m llmc.mcgrep "authentication" --emit-training
```

This outputs JSON showing the tool schema + invocation + response, suitable for fine-tuning.

### Quick Heuristics

- **`skeleton` + `nav read`:** Best for code modification tasks. Start with the map, snipe what you need.
- **`mcinspect` vs `read_file`:** Always prefer `mcinspect` for code. It gives you the **graph** (callers/deps) and **summary** instantly.
- **`mcgrep`:** If results are weird, try more literal queries or fallback to `rg`.
- **`llmc debug doctor`:** Your first step if the RAG system seems broken.

---

## 5.5 OpenAI Tool Calling Convention

**The Insight:** LLMs have been trained extensively on OpenAI function calling format. LLMC tools follow this format, so there's zero learning curve.

### Why This Matters

**Before (Expensive):**
```markdown
## Tools
Here are 30 tools with their schemas...
[10KB of JSON definitions]
```

**After (Cheap):**
```markdown
## Tools
Use OpenAI-standard tool calling. Available locally:
- mcgrep <query> - semantic code search
- mcwho <symbol> - find callers/callees
- mcinspect <symbol> - deep inspection
```

### The Pattern

Models already know `{"name": "...", "arguments": {...}}` format from training. Just tell them the tool names → they infer the schema.

### MCP Equivalents

| CLI Tool | MCP Tool | OpenAI Schema |
|----------|----------|---------------|
| `mcgrep` | `rag_search` | `{"name": "rag_search", "arguments": {"query": "..."}}` |
| `mcwho` | `rag_where_used` | `{"name": "rag_where_used", "arguments": {"symbol": "..."}}` |
| `mcinspect` | `inspect` | `{"name": "inspect", "arguments": {"symbol": "..."}}` |
| `mcread` | `read_file` | `{"name": "read_file", "arguments": {"path": "..."}}` |
| `mcrun` | `run_cmd` | `{"name": "run_cmd", "arguments": {"cmd": "..."}}` |

Same instructions work for MCP, CLI, or local execution.

---

## 6. Limits and Thresholds

### 6.1 `--limit` (How Many Candidates)

`--limit` controls how many hits you pull back.

**For `search`:**

- Start with `--limit 20–30`.
- Use `--limit 10` when:
  - The query names a specific function/class/module.
  - Dave already pointed at a file or path.
- Use `--limit 40–50` when:
  - Change is cross-cutting (config keys, logging, error messages).
  - Dave says “all places”, “all usages”, “everywhere”.

**For `plan`:**

- Start with `--limit 40–50` for non-trivial changes.
- Use `--limit 20` for very focused edits.
- Use `--limit 80–100` only when you expect many affected files  
  (e.g. rename a core API, change a base class).

Heuristic:

- If results look **thin** and you know the repo is larger → increase `--limit`.
- If you’re drowning in irrelevant files → decrease `--limit`.

### 6.2 `--min-score` (Advanced; Rarely Needed)

Similarity scores are noisy and relative.

- **Default:** Don’t set `--min-score` unless you have a specific reason.
- Use it only to trim obviously bad tails when:
  - The top hit(s) are clearly right.
  - The long tail is clearly junk.

Workflow:

1. Run without `--min-score`.
2. If top hits look correct and the rest are junk:
   - Note the top score (e.g. `0.86`).
   - Re-run with `--min-score` slightly below it (e.g. `--min-score 0.82`).
3. If `--min-score` gives no results but you expect matches:
   - Remove it and fall back to the defaults.

Never:

- Never interpret the score as “percent confidence”.
- Never assume “no results above threshold” means “nothing exists in the repo”.

### 6.3 `--min-confidence` (LLM Planning Confidence)

Some `plan` outputs can include an LLM-derived confidence per item.

- **Default:** `--min-confidence 0.5` is usually fine.
- Raise toward `0.7` when:
  - Editing critical infra, security-sensitive code, or deployment paths.
  - You want only high-signal suggestions and will accept missing some candidates.
- Lower toward `0.3` when:
  - Exploring, prototyping, or willing to manually filter more noisy candidates.

Heuristic:

- For **production-critical** edits → you may increase `--min-confidence`, but still verify manually.
- For **exploratory** work → moderate or low thresholds are fine; human judgment is required either way.

---

## 7. Recommended Flows

### Flow 0 – Codebase Orientation (Start Here)

Before diving into code, get the 30-second mental model:

```bash
python3 -m llmc.mcschema
```

This returns a ~400 token manifest with:
- Entry points (CLIs, servers)
- Module breakdown with purposes
- Hotspot files (most connected) with descriptions

**Use this before any other search.** It tells you where to look.

### Flow 0.5 – Mechanical Context (For Code Modification)

When your task involves **modifying code**, use the Skeleton + Sniper pattern:

1. **Get the Skeleton (Global Map):**

   ```bash
   python3 -m llmc.rag.cli skeleton --limit 100
   ```

   This returns **signatures + docstrings only** (no implementation bodies).
   You now know what exists and where it's defined.

2. **Snipe the Implementation (Surgical Read):**

   When you see a symbol you need to modify or understand:

   ```bash
   python3 -m llmc.rag.cli nav read Skeletonizer._handle_class
   ```

   This returns **only the 20-50 lines** of that specific method.

3. **Check Impact Before Editing:**

   ```bash
   python3 -m llmc.rag.cli nav where-used bulk_insert_nodes
   ```

   This tells you what will break if you change the signature.

**Why this flow:**
- Skeleton is ~2,000 tokens for 100 files (vs 200,000+ for full source)
- Each `nav read` is ~50-100 tokens (vs 2,000+ for full file reads)
- You get "Instant Omniscience" without context window bloat

### Flow A – LLM-Optimized Search (Primary)

LLMs need **full file context**, not just snippets. Use mcgrep with `--expand` first:

1. **Find files semantically with full content:**

   ```bash
   python3 -m llmc.mcgrep "authentication logic" --expand 3
   ```

   This returns full file content for the top 3 semantically-matched files,
   with matched line ranges highlighted.

2. **If you need ALL spans for a specific file:**

   ```bash
   python3 -m llmc.rag.cli search "auth" --path src/auth.py --limit 100
   ```

   Use high `--limit` to get all spans, not just 10-20.

3. **For symbol details + graph relationships:**

   ```bash
   python3 -m llmc.mcwho EnrichmentPipeline    # Quick: who calls/uses this?
   python3 -m llmc.mcinspect EnrichmentPipeline # Deep: full symbol context
   ```

### Flow B – Quick Span Search (Narrow Queries)

When you already know roughly where to look:

1. Run mcgrep:

   ```bash
   python3 -m llmc.mcgrep "database connection pool"
   ```

   Shows top 20 files with descriptions + top 10 spans with context.

2. Skim top hits by **path + description + spans**.
3. If results look wrong:
   - Refine the query (more literal, include identifiers).
   - Or fall back to `rg` / AST tools.

4. Once you know where the logic lives, use `python3 -m llmc.mcgrep --expand 3` to get full context.

### Flow C – Plan Edits

1. Run `plan`:

   ```bash
   python3 -m llmc.rag.cli plan "short description of change" --limit 50 --min-confidence 0.5
   ```

2. Inspect planned targets:
   - If most look right → treat as starting worklist.
   - If many look wrong → adjust query, limits, or skip the plan and fall back to manual search.

3. Edit code, then run tests / smoke checks per **CONTRACTS.md** and section 8 below.

### mc* CLI Quick Reference

See **Section 6** for the authoritative `mc*` CLI table. All commands:

```bash
python3 -m llmc.mcschema              # Codebase orientation
python3 -m llmc.mcgrep "query"        # Semantic search
python3 -m llmc.mcwho Symbol          # Who calls/uses this?
python3 -m llmc.mcinspect Symbol      # Deep inspection + graph
python3 -m llmc.mcread path/to/file   # Read with context
python3 -m llmc.mcrun "command"       # Execute with logging
```

---

## 8. Testing Rules

**When to Test**

- Test whenever you touch:
  - Code
  - Scripts
  - Anything executable
- You MAY skip tests when changes are strictly:
  - Docs-only
  - Comments-only
  - Config-only (where config doesn’t affect runtime behavior in this environment)

If tests can’t be run here, report:

```text
TESTING SKIPPED: <reason>
```

…and stop.

**How to Test (Baseline)**

1. Restart or reload the affected service/module when that’s the normal flow.
2. Hit the target using the lightest tool:
   - `pytest` for unit/integration tests
   - `curl` for HTTP APIs
   - minimal CLI invocation for CLIs
3. Check logs when available.
4. Spot-check UI when changes are user-facing.

**What to Output**

- `Tests: PASSED <summary>`
- `Tests: SKIPPED (<reason>)`
- `Tests: FAILED (<reason> + suggested next step)`

---

## 9. Jules Protocol (Async Agent Delegation)

Jules is an external async coding agent. Use it to parallelize well-scoped tasks.

### When to Use Jules

- Documentation validation/fixes
- Well-defined refactoring with clear acceptance criteria
- Adding tests for existing code
- CLI improvements with existing patterns to follow

### When NOT to Use Jules

- Security-critical changes (keep in-house)
- Complex architectural decisions
- Tasks without clear patterns to follow

### Task Description Format

Include in your task description:
1. **Goal** - What we're trying to achieve
2. **Problem** - Why this needs to change
3. **Changes Required** - Specific files and modifications
4. **Reference Files** - Patterns to follow
5. **Tests** - Required test coverage
6. **Acceptance Criteria** - How to know it's done

### CLI Commands

```bash
# Create a new task
jules remote new --repo vmlinuzx/llmc --session "Task description"

# List all sessions
jules remote list --session

# Preview changes (just show diff)
jules remote pull --session <id>

# Apply changes to local repo
jules remote pull --session <id> --apply
```

### Review Process (Agent Responsibility)

When a task shows "Awaiting User Feedback":

1. **Preview:** `jules remote pull --session <id>`
2. **Review the diff:**
   - Does the code follow existing patterns?
   - Are the changes correct?
   - Does it match the acceptance criteria?
3. **Apply:** `jules remote pull --session <id> --apply`
4. **Commit and push** the changes

**Do NOT ask the user to review Jules tasks** - this is the agent's responsibility.

---

## 10. Stop / Block Conditions

Stop and report `BLOCKED` instead of guessing when:

- `CONTRACTS.md` is missing or clearly out of sync with **AGENTS.md**.
- Required sections referenced in either doc are missing.
- Repo layout is drastically different from what the docs describe.

Message format:

```text
BLOCKED: <short reason>. Waiting for Dave.
```

---

## 11. Scope Discipline

- One **focused** changeset per request unless Dave explicitly widens scope.
- Stay inside the repo (`/home/$USER/src/llmc`) unless instructed otherwise.
- Prefer diffs and incremental changes over giant rewrites.

---

## 12. After Reading This

After loading this file:

1. Read **CONTRACTS.md** for environment, install policy, tmux policy, and task protocol.
2. Respect both documents together:
   - **AGENTS.md** → behavior and workflows.
   - **CONTRACTS.md** → constraints and environment.

You now understand the rules. Try not to piss off Future Dave.
