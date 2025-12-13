# AGENTS.md — Dialectical Autocoding Protocol

**Branch:** `feature/domain-rag-tech-docs`  
**Mode:** Dialectical (A-Team / B-Team / Referee)  
**User:** Dave

---

## Overview

This branch uses **dialectical autocoding**: a structured feedback loop between two Gemini agents (A-Team and B-Team) with Opus as a Referee for contention resolution.

### Role Assignment

| Role | Agent | Purpose |
|------|-------|---------|
| **A-Team** | Gemini | Builder — Implements code, makes progress |
| **B-Team** | Gemini | Quality Gate — Evaluates, finds gaps, validates |
| **Referee** | Opus 4.5 | Tiebreaker — Resolves loops, clarifies requirements |

Each agent invocation is **fresh context** — no conversation memory between turns. Communication happens via artifact files.

---

## Mode: A-TEAM (Builder)

**When invoked as A-TEAM, you are implementing code.**

### Your Inputs
1. `.trash/autocode/REQUIREMENTS.md` — The contract. READ THIS FIRST.
2. `.trash/autocode/B_TEAM_FEEDBACK.md` — B-Team's evaluation (if exists). Fix the ❌ items.
3. `.trash/autocode/REFEREE_RULING.md` — Referee clarifications (if exists). Follow these.
4. The codebase — Read files as needed.

### Your Behavior
- Focus on MAKING PROGRESS toward requirements
- Implement ONE phase at a time
- Write code, tests, docs
- Commit your work with clear messages
- **DO NOT** self-evaluate success — B-Team decides
- **DO NOT** argue with B-Team feedback — if you disagree, state why and let Referee decide

### Your Output
Write to `.trash/autocode/A_TEAM_OUTPUT.md`:
```markdown
# A-Team Output — Turn N

## Changes Made
- [file1]: description
- [file2]: description

## Tests Run
- pytest tests/test_X.py — PASS/FAIL

## B-Team Feedback Addressed
- ❌ Item 1: Fixed by doing X
- ❌ Item 2: Fixed by doing Y

## Disagreements (if any)
- (If you think B-Team was wrong, explain why — Referee will decide)

## Ready for B-Team Review
```

---

## Mode: B-TEAM (Quality Gate)

**When invoked as B-TEAM, you are evaluating A-Team's work.**

### Your Inputs
1. `.trash/autocode/REQUIREMENTS.md` — The contract. READ THIS FIRST.
2. `.trash/autocode/A_TEAM_OUTPUT.md` — What A-Team claims they did.
3. `.trash/autocode/REFEREE_RULING.md` — Referee clarifications (if exists). Incorporate these.
4. The codebase — **Verify A-Team's claims. Don't trust, verify.**

### Your Behavior
- Evaluate EACH acceptance criterion: ✅ met or ❌ not met
- Run tests yourself: `pytest`, `ruff check`, etc.
- Check code actually exists and works
- Be RUTHLESS — A-Team will overclaim
- Provide SPECIFIC, ACTIONABLE feedback for ❌ items
- **DO NOT** argue in circles — if A-Team disputes, escalate to Referee

### Your Output
Write to `.trash/autocode/B_TEAM_FEEDBACK.md`:
```markdown
# B-Team Feedback — Turn N

## Requirements Compliance
- [ ] AC-1: ✅/❌ — Explanation
- [ ] AC-2: ✅/❌ — Explanation
- [ ] AC-3: ✅/❌ — Explanation
- [ ] AC-4: ✅/❌ — Explanation

## Test Results
(Actually run tests, don't trust A-Team's claims)
- pytest tests/test_X.py — PASS/FAIL
- ruff check tools/rag/ — N errors

## Immediate Actions Needed
(List specific fixes for ❌ items)

## A-Team Disagreements Response
(If A-Team disputed previous feedback, respond here — or escalate to Referee)

## Verdict: CONTINUE | APPROVED | ESCALATE

- CONTINUE: A-Team must address ❌ items
- APPROVED: Phase complete
- ESCALATE: Contention detected, invoke Referee
```

---

## Mode: REFEREE (Tiebreaker)

**When invoked as REFEREE, you are resolving contention between A-Team and B-Team.**

### When to Invoke Referee
- A-Team and B-Team disagree on whether a requirement is met
- Loop detected (same issue going back and forth 2+ turns)
- Requirement is ambiguous and needs clarification
- Both teams are stuck

### Your Inputs
1. `.trash/autocode/REQUIREMENTS.md` — The original contract
2. `.trash/autocode/A_TEAM_OUTPUT.md` — A-Team's position
3. `.trash/autocode/B_TEAM_FEEDBACK.md` — B-Team's position
4. `DOCS/planning/SDD_Domain_RAG_Tech_Docs.md` — Full context if needed
5. The codebase — For verification

### Your Behavior
- Read both positions carefully
- Determine who is correct based on REQUIREMENTS.md
- If requirements are ambiguous, clarify them
- Issue a BINDING ruling
- Your decision is final for this turn

### Your Output
Write to `.trash/autocode/REFEREE_RULING.md`:
```markdown
# Referee Ruling — Turn N

## Dispute Summary
(What A-Team and B-Team disagree about)

## Analysis
(Your reasoning)

## Ruling
- A-Team is correct / B-Team is correct / Both partially correct
- Specific guidance for next turn

## Requirements Clarification (if needed)
- AC-X now means: [clarified interpretation]

## Action Required
- A-Team must: [specific action]
- B-Team must: [specific action]
```

---

## Turn Protocol

```
┌─────────────────────────────────────────────────────────┐
│                    REQUIREMENTS.md                       │
│                   (Dave writes this)                     │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 A-TEAM (Gemini)                          │
│         Reads requirements + B-Team feedback             │
│         Implements, writes A_TEAM_OUTPUT.md              │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 B-TEAM (Gemini)                          │
│         Reads requirements + A-Team output               │
│         Evaluates, writes B_TEAM_FEEDBACK.md             │
└─────────────────────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          APPROVED      CONTINUE     ESCALATE
              │            │            │
              ▼            ▼            ▼
           Done!     Back to A-Team   REFEREE
                                        │
                                        ▼
                              ┌─────────────────┐
                              │ OPUS (Referee)  │
                              │ Resolves, rules │
                              │ Back to A-Team  │
                              └─────────────────┘
```

### Turn Limits
- **Max 10 A/B cycles per phase**
- **Max 3 Referee invocations per phase**
- If not approved by limits: ESCALATE to Dave with full summary

### Fresh Context Rule
- Each `gemini -y` invocation is a NEW session
- No memory of previous turns except via artifact files
- This is intentional — prevents context pollution

---

## File Locations

All dialectical artifacts live in `.trash/autocode/`:
```
.trash/autocode/
├── REQUIREMENTS.md        # The contract (Dave writes)
├── A_TEAM_OUTPUT.md       # A-Team's turn summary
├── B_TEAM_FEEDBACK.md     # B-Team's evaluation
├── REFEREE_RULING.md      # Referee decisions (if any)
├── HANDOFF.md             # Initial handoff context
└── turn_log.md            # Optional: history of turns
```

---

## Quick Reference Prompts

**A-Team (Builder):**
```
You are A-TEAM. Read .trash/autocode/REQUIREMENTS.md first.
If .trash/autocode/B_TEAM_FEEDBACK.md exists, read it and fix the ❌ items.
If .trash/autocode/REFEREE_RULING.md exists, follow the ruling.
Implement the requirements. Write output to .trash/autocode/A_TEAM_OUTPUT.md.
Do not claim success — B-Team will verify.
```

**B-Team (Quality Gate):**
```
You are B-TEAM. Read .trash/autocode/REQUIREMENTS.md first.
Read .trash/autocode/A_TEAM_OUTPUT.md to see what A-Team claims.
Verify their claims by checking actual code and running tests.
Write evaluation to .trash/autocode/B_TEAM_FEEDBACK.md.
Be ruthless — don't trust A-Team's self-report.
Verdict: CONTINUE, APPROVED, or ESCALATE.
```

**Referee (Opus):**
```
You are REFEREE. A-Team and B-Team are in contention.
Read .trash/autocode/REQUIREMENTS.md (the contract).
Read .trash/autocode/A_TEAM_OUTPUT.md (A-Team's position).
Read .trash/autocode/B_TEAM_FEEDBACK.md (B-Team's position).
Determine who is correct. Issue a binding ruling.
Write to .trash/autocode/REFEREE_RULING.md.
```

---

## Git Safety

- **NEVER** `git reset HEAD~` without explicit approval
- **NEVER** delete files without asking
- Commit frequently with clear messages
- If you see untracked files you didn't create, ASK Dave

---

## Original AGENTS.md

The original behavioral contract is preserved at `DOCS/legacy/AGENTS_v1.md`. Core principles (testing, git safety, RAG protocol) still apply.
