# AGENTS.md – LLMC Repo Agent Contract

> This file defines how **automated agents** (Claude Desktop Commander, Codex, VS Code / MCP plugins, CLI bots, etc.) must behave when operating in this repo.
>
> If you are an agent reading this: **stop guessing and follow this doc.**


---

## 1. Scope & Priority

When you are working inside this repo:

1. This `AGENTS.md` is your **behavior contract**.
2. `CONTRACTS.md` defines the **environment, hazards, and tool constraints**.
3. Other docs (e.g. `DOCS/…`) are **reference material**, not behavior contracts.

**Read order on session start:**

1. `AGENTS.md` (this file – how to behave)
2. `CONTRACTS.md` (execution / environment rules, Tool Envelope details)
3. If you need more background on RAG or Desktop Commander integration, peek at:
   - `DOCS/DESKTOP_COMMANDER_INTEGRATION.md`
   - Any SDD/HLD docs relevant to the feature you are changing


---

## 2. Session Startup Checklist (All Agents)

On a new session in this repo, you MUST:

1. **Identify the human** as **Dave**.
2. **Confirm the repo root** is correct (usually `/home/vmlinux/src/llmc` on Dave’s box).
3. Open and skim:
   - `AGENTS.md` (this file)
   - `CONTRACTS.md`
4. Build a **brief internal summary** of:
   - Execution rules (Tool Envelope / TE, test policies)
   - RAG usage expectations
   - Any “do not touch” areas or high-risk zones called out in `CONTRACTS.md`

Do **not** dump a huge recap of these docs back to Dave unless he explicitly asks. Use them as **operational rules**, not content to regurgitate.


---

## 3. Repo & Environment Assumptions

- Canonical repo root (Dave’s main dev box):  
  `/home/vmlinux/src/llmc`
- Python commands should assume the local venv / poetry environment as defined in `CONTRACTS.md` or tooling scripts.
- If you need to run something that might affect the environment (install packages, edit configs, etc.), check `CONTRACTS.md` first and **ask Dave** if it looks risky.

If you are unsure whether you are in the correct repo, run a read-only command via TE, such as:

```bash
cd /home/vmlinux/src/llmc   && export TE_AGENT_ID="<your-agent-id>"   && ./scripts/te git status --short
```


---

## 4. Tool Envelope (TE) – Command Execution Contract

### 4.1 Required TE usage

If you are an agent (Claude DC, VS Code, Codex, Minimax, etc.), then:

- **All shell commands in this repo** should go through the TE wrapper:
  - Wrapper script: `./scripts/te`
  - Telemetry DB: `.llmc/te_telemetry.db`
- Your shell commands must generally follow this pattern:

```bash
cd /home/vmlinux/src/llmc   && export TE_AGENT_ID="<agent-slug>"   && ./scripts/te <command> [args...]
```

### 4.2 TE_AGENT_ID

Set a stable **agent slug**:

- `claude-dc`   – Claude Desktop Commander
- `codex-cli`   – Codex / VS Code / CLI orchestrator
- `minimax-cli` – Minimax-based CLI agent
- `gpt-chat`    – ChatGPT via browser (if you’re proposing commands for Dave)
- `manual-dave` – Reserved for Dave when he wants his own commands logged

If you forget `TE_AGENT_ID`, TE might still execute but telemetry becomes low-value. Treat missing `TE_AGENT_ID` as a bug and fix it on the next command.

### 4.3 When TE MUST be used

Use TE for **all** of the following:

- Running tests (unit, integration, CLI smoke tests).
- Running LLMC/RAG tools (`tools.rag.cli`, `scripts/*` helpers).
- Doing large-scale inspection like `rg`, `grep`, `find` over the repo.
- Any command that modifies files in the repo.

### 4.4 When TE MAY be bypassed

Bypassing TE is **exception-only**:

1. `./scripts/te` is clearly broken or missing, **and**
2. You have called out a `BLOCKED_BY_TE` condition in your response, **and**
3. Dave explicitly authorizes a temporary bypass.
4. Interactive applications.  

If bypassing TE:

- Prefer `./scripts/te -i <command> ...` for “raw” pass-through when available.
- Otherwise, run the minimal command directly and **state explicitly** in your response that you bypassed TE and why.

Never silently ignore TE failures.


---

## 5. RAG & Context Policy

This repo has a full **RAG + schema graph** stack. Your job is to **use it** instead of slurping whole files by default.

### 5.1 Default: RAG-first

When you need to understand code or docs:

1. Use semantic search via TE:

   ```bash
   ./scripts/te python3 -m tools.rag.cli search "your question or concept" --limit 5 --json
   ```

2. For more complex “how does X work?” queries, use `plan`:

   ```bash
   ./scripts/te python3 -m tools.rag.cli plan "How does the enrichment pipeline work?"
   ```

3. For structure-aware navigation and freshness-aware search:

   ```bash
   ./scripts/te python3 -m tools.rag.cli nav search "schema enrichment" /home/vmlinux/src/llmc
   ```

### 5.2 When full-file reads are allowed

Reading entire files (or many large files) is allowed only when:

- RAG returns nothing or clearly-misleading results, **and**
- You note in your explanation to Dave that you had to fall back to direct file reads.

Preferred pattern:

1. RAG search for relevant spans.
2. If needed, open the file(s) containing those spans for surrounding context.
3. Only if that fails, consider whole-file / multi-file reads.


---

## 6. Change Management (“Dave Protocol”)

When making changes in this repo, follow this workflow unless Dave explicitly says to shortcut it.

### 6.1 Classify the change

- **Trivial** (typo, log message, comment tweak, very small refactor with no behavioral change):
  - You may skip a formal SDD but still briefly state the intent and affected files, and get permission to continue.
- **Non-trivial** (new behavior, touching core RAG/TE logic, changes that affect indexing, enrichment, routing, or telemetry):
  - You should produce a **small SDD or change sketch** before editing code.

### 6.2 Mini-SDD structure

For non-trivial work, write a **brief Mini-SDD** (can be in the chat or as a `.md` under `DOCS/SDD/`):

- **Goal:** What problem are you solving?
- **Scope:** Which components / modules will be touched?
- **Plan:** 2–4 steps or phases (e.g. “Phase 1: add config; Phase 2: wire to TE; Phase 3: tests and docs”).
- **Risks:** Anything that might break RAG, TE, or production behavior.

### 6.3 Implement in small phases

Implement changes in **small, testable phases**:

1. Phase 1: add or adjust configuration / interfaces.
2. Phase 2: wire new behavior without ripping out the old until tests pass.
3. Phase 3: tighten tests, clean up dead code, improve docs.
4. Phase 4: optional refactor / polish (only if previous phases are stable).

Do not refactor half the repo in one go. Dave has to be able to **review diffs** without going insane.

### 6.4 Testing expectations

Before claiming success on a change, you must:

1. Run the appropriate tests via TE, e.g.:

   ```bash
   ./scripts/te pytest tests/test_enrichment_adapters.py -q
   ./scripts/te pytest tests/ -q
   ./scripts/te python3 -m tools.rag.cli doctor
   ```

   (The exact commands depend on the area you touched – use `CONTRACTS.md` and existing docs as guidance.)

2. In your response to Dave, list:
   - The commands you ran
   - Whether they passed or failed
   - Any important output (summarized, not full logs unless asked)

If tests fail, **do not** claim the change is complete. Report the failure and either fix it or clearly mark it as a known issue.

### 6.5 Patch delivery for non-executing agents

If you are **not** directly editing the filesystem (e.g. you’re ChatGPT in a browser and Dave will apply changes manually), then:

- Prefer to deliver changes as a **zip-friendly patch layout**:
  - Correct repo-relative paths
  - Whole-file contents for new/changed files
- Follow any explicit instructions Dave gives about patch format (e.g. “zip with SDD + impl notes in DOCS/”).
- Keep your inline code snippets minimal and coherent – they should match the files in the patch.


---

## 7. Risky Operations & Guardrails

You **must not**:

- Run destructive commands like:
  - `rm -rf /`
  - `rm -rf .git`
  - `git clean -xdf` (unless Dave explicitly approves).
- Touch unrelated system directories (`/etc`, `/var`, `$HOME` outside this repo) unless explicitly instructed.
- Alter production-like configs (e.g. real API keys, real production endpoints) without explicit sign-off.

Be extra cautious when:

- Modifying anything under a `prod`, `live`, or `*_PROD` directory.
- Changing anything that affects how TE or RAG index multiple repos.

If something feels like it could take down Dave’s day job or data, **ask first**.


---

## 8. Desktop Commander–Specific Rules (Claude DC)

If you are **Claude running via Desktop Commander**:

1. Assume repo root: `/home/vmlinux/src/llmc` (unless Dave tells you otherwise).
2. On session start:
   - Open `AGENTS.md` and `CONTRACTS.md`.
   - Confirm `./scripts/te` exists and is executable.
3. For every command you run in this repo:
   - Use the TE pattern with `TE_AGENT_ID="claude-dc"`:

     ```bash
     cd /home/vmlinux/src/llmc        && export TE_AGENT_ID="claude-dc"        && ./scripts/te <command> [args...]
     ```

4. For code understanding:
   - Prefer RAG (`tools.rag.cli` search/plan/nav) via TE.
   - Only fall back to full-file reads when RAG is insufficient and you’ve said so.

5. For code changes:
   - Follow the “Dave Protocol” above (Mini-SDD → phased changes → tests).
   - Run tests via TE before claiming completion.
   - Summarize what you changed and what you executed.

6. For long-running tasks:
   - Prefer short, single-shot TE commands over starting new daemons or background jobs.
   - If you absolutely must start something long-lived, clear it with Dave and respect any tmux/job guidelines in `CONTRACTS.md`.


---

## 9. Other Orchestrators (Codex, VS Code, Minimax, etc.)

If you are **not** Desktop Commander but still an automated agent interacting with this repo:

- All of the above still applies except for the specific `TE_AGENT_ID` value – use an appropriate slug.
- If you propose commands for Dave to run manually (e.g. in ChatGPT chat), write them **already TE-wrapped** so he can copy-paste:
  
  ```bash
  cd /home/vmlinux/src/llmc     && export TE_AGENT_ID="gpt-chat"     && ./scripts/te pytest tests/test_something.py -q
  ```

- If your environment cannot actually execute commands (e.g. browser-only agents), make that clear and focus on:
  - Good Mini-SDDs
  - Clean patches
  - TE-wrapped commands for Dave to run himself


---

## 10. If In Doubt

If you are ever unsure about:

- Whether you should use TE
- Whether RAG is appropriate
- Whether a change is too big
- Whether something might break real systems

Then do the following:

1. **Stop.**
2. Explain the uncertainty clearly to Dave.
3. Propose 1–2 options (e.g. “safe minimal fix” vs. “bigger refactor”).
4. Wait for direction.

Your job as an agent in this repo is not to be clever; it is to be **predictable, safe, and useful** under these rules.
