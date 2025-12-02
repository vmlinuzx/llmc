# LLMC Feature Delivery Workflow (HLD → SDD → Phases → Agent Pick)

Version: 0.1  
Owner: DC + Chat Copilot  

---

## 0. Preflight – What Are We Doing?

Before touching models:

1. Name the thing: short, imperative (e.g., `“Configurable Embedding Backends v2”`).
2. One‑liner goal: “Who benefits and how?”
3. Guardrails:
   - Hard constraints (perf, latency, cost ceiling, backwards compat).
   - No‑go zones (files / systems we **will not** touch in this round).

Write this in a short `GOAL:` block at the top of HLD/SDD.

---

## 1. Create HLD

The HLD is the “how this hangs together” doc, not the code recipe.

### 1.1 HLD Skeleton

For every feature:

1. **Problem Statement**
2. **Current State**
3. **Target State**
4. **Key Design Decisions**
5. **Risks / Trade‑offs**
6. **Out of Scope**

Keep it 1–3 pages max.

### 1.2 Decide if it deserves a Research Doc (1.a)

Create a separate research doc *if any* of these are true:

- New domain or external API you don’t already know well.
- Non‑trivial algorithm choice (ranking, embeddings, batching, async, etc.).
- Multiple viable architectures that need comparison.
- Anything where “future Dave” will ask “why the hell did Past Dave do this?”

If yes:

- File: `DOCS/RESEARCH/<feature_name>.md`
- Sections:
  1. Context / Problem
  2. Relevant prior art (links, quotes, screenshots)
  3. Options (A/B/C) with pros/cons
  4. Decision + Why
  5. Open questions / TODOs

### 1.3 5.0 Extended Thinking Pass (1.a.1)

Once the research doc exists:

1. Feed the research doc to your “extended thinking” model (me).
2. Ask it to:
   - Sanity‑check assumptions.
   - Rebuild/upgrade the HLD from research.
   - Call out hidden risks, migration concerns, or config pitfalls.
3. The output is **HLD v2**, which becomes the source of truth for the SDD.

---

## 2. Create SDD (Implementation Blueprint)

The SDD is the “turn this into code and tests” spec.

Minimum sections:

1. **Scope & Constraints**
2. **Data & Schema Changes**
3. **Config Surfaces / Flags**
4. **APIs & Interfaces**
5. **File‑Level Change Plan**
6. **Testing Strategy**
7. **Rollout / Migration Plan**
8. **Backout Plan**

For each file/function:

- What to add/change/remove.
- Inputs, outputs, side‑effects.
- Any non‑obvious edge cases.

The SDD should be detailed enough that “junior AI dev” (any code model) can implement phases without inventing new behavior.

---

## 3. Break SDD into Phases + Complexity Matrix

### 3.1 Phase Design Rules

When carving phases:

- Each phase should be **independently mergeable**.
- Each phase should have **clear tests** (even if written later).
- Avoid phases that touch everything everywhere.
- Prefer vertical slices (config → code → tests → docs) over random file grab‑bags.

Name phases like:

- `P1 – Config surface + plumbing only`
- `P2 – Core logic implementation`
- `P3 – Tests + safety rails`
- `P4 – Refactors / cleanup`

### 3.2 Complexity Matrix Per Phase

For each phase, assign:

#### 3.a. Context Pressure (CP)

- **Low** – Can be solved with just the file in question.
- **Med** – Needs imports + immediate neighbors (1‑hop graph).
- **High** – Needs global understanding (config patterns, DB schema, cross‑module state).

**Implication:**  
High CP → RAG plan or big‑context model (Gemini 1.5 Pro / Claude 3.5 / GPT‑5.1 Thinking).

#### 3.b. Testability Index (TI)

- **High** – Pure-ish logic, deterministic, easy unit test.
- **Med** – Integration required, mocks needed (network/IO).
- **Low** – State‑dependent, racey, side‑effects, timing, daemon/service behavior.

**Implication:**  
Low TI → Write test plan first with your “Ruthless Tester” model (e.g., Minimax) before any code gets shipped.

#### 3.c. Destructive Potential (DP)

- **Safe** – Additive only (new file, new function, new config flag).
- **Caution** – Modifies existing logic / behavior but no schema or deletes.
- **Hazard** – Schema migrations, file deletion, overwrite logic, data moves.

**Implication:**  
Hazard DP → Mandatory human review + dry‑run / migration scripts.

### 3.3 Optional: Score It

If you want a crude “oh shit” score:

- CP: Low=1, Med=2, High=3
- TI: High=1, Med=2, Low=3
- DP: Safe=1, Caution=2, Hazard=3

Phase Risk = CP + TI + DP (3–9)

Sort phases by descending risk to know where you (the human) must stay in the loop.

---

## 4. Pick Who Codes Each Phase (Agent Routing)

Use CP / TI / DP to decide **who** should implement.

### 4.1 Heuristics

- **Low CP, High TI, Safe DP**
  - Great for local/cheap code models or “junior dev” LLM.
  - You can largely auto‑implement with light review.

- **Med CP, Med TI, Caution DP**
  - Use stronger code model + strict tests.
  - Require test updates in the same phase.

- **High CP (any TI), Caution/Hazard DP**
  - You (human) or high‑end reasoning model must drive design edits.
  - Implementation may be shared, but review and diffs are human‑gated.
  - Consider separate “migration phase” with scripts that can run in dry‑run mode.

- **Low TI + Hazard DP**
  - This is “do not let a feral LLM off the leash.”
  - Sequence:
    1. Ruthless Tester model writes test plan + safety checks.
    2. Design validated by you.
    3. Implementation done very incrementally, with tests run after each chunk.

### 4.2 Simple Routing Table

For each phase, once you fill CP/TI/DP:

- Decide:
  - **Planner:** which reasoning model (if any) to refine SDD fragment.
  - **Coder:** which code‑heavy model (local vs cloud) to write patches.
  - **Tester:** who designs test cases (you vs ruthless tester model).
  - **Gatekeeper:** usually you; auto‑merge only for low‑risk phases.

Capture this in a tiny table per phase, e.g.:

| Phase | CP | TI | DP | Planner | Coder | Tester | Gatekeeper |
|-------|----|----|----|---------|-------|--------|------------|
| P1    | Low| High|Safe| GPT‑5.1 | Qwen 7B | Minimax | You |
| P2    | Med| Med |Caution| GPT‑5.1 | Claude Code | Minimax | You |
| P3    | High| Low|Hazard| GPT‑5.1 | Human+LLM pair | Minimax | You |

---

## How to Use This in Practice

For each new chunk of work:

1. Draft HLD.
2. Decide if research doc is needed; if yes, write it.
3. Run extended thinking pass to refine HLD.
4. Write SDD from refined HLD.
5. Break SDD into phases and assign CP/TI/DP.
6. Fill in the routing table for each phase.
7. Execute phases in order, keeping you in the loop where risk is highest.

Rinse, repeat, and tweak the heuristics as you see where the pain actually is.
