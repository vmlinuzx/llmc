# HANDOFF: Opus Orchestrator — Dialectical Autocoding

**Your Role:** Orchestrator (Opus 4.5)  
**Your Workers:** A-Team (Gemini), B-Team (Gemini)  
**Branch:** `feature/domain-rag-tech-docs`

---

## ⚠️ ARCHITECTURE: You Are The Conductor

You are **NOT** a passive referee waiting for escalation.  
You are **THE ORCHESTRATOR** — you invoke agents, read their output, and decide what happens next.

```
┌─────────────────────────────────────────────────────────────┐
│                     OPUS 4.5 (YOU)                          │
│                    THE ORCHESTRATOR                         │
│         Invoke agents → Read summaries → Decide next        │
└─────────────────────────────────────────────────────────────┘
                    │                    │
         ┌─────────┘                    └─────────┐
         ▼                                        ▼
   ┌───────────┐                            ┌───────────┐
   │ gemini -y │                            │ gemini -y │
   │  A-TEAM   │                            │  B-TEAM   │
   │ (builder) │                            │ (verifier)│
   └───────────┘                            └───────────┘
         │                                        │
         └──────────► artifact files ◄────────────┘
                          │
                          ▼
                   YOU READ THESE
                   YOU DECIDE NEXT
```

---

## The Loop (You Execute This)

**THIS IS FULLY AUTONOMOUS. No stopping to check with Dave. Run until terminal state.**

```
FOR turn IN 1..10:
    1. Run: gemini -y "A-TEAM prompt..." >/dev/null 2>&1
       ⚠️ CRITICAL: Redirect ALL output to /dev/null or it floods YOUR context!
    2. Read ONLY the last 5 lines: tail -5 DOCS/planning/autocode/A_TEAM_OUTPUT.md
       → Look for "SUMMARY: ..." line
    3. Run: gemini -y "B-TEAM prompt..." >/dev/null 2>&1
    4. Read ONLY the last 5 lines: tail -5 DOCS/planning/autocode/B_TEAM_FEEDBACK.md
       → Look for "VERDICT: ..." and "SUMMARY: ..." lines
    
    5. DECIDE based on VERDICT:
       - APPROVED → STOP. Write final success summary to turn_log.md.
       - CONTINUE → Next turn. Invoke A-Team again.
       - ESCALATE → YOU make a ruling, write REFEREE_RULING.md, invoke A-Team.
       - LOOP DETECTED (same issue 2+ turns) → STOP. Write failure analysis to turn_log.md.

IF turn == 10 AND not APPROVED:
    → STOP. Write "MAX TURNS REACHED" + blockers to turn_log.md.
```

---

## Invoking A-Team

```bash
# ⚠️ ALWAYS redirect output: >/dev/null 2>&1
gemini -y "You are A-TEAM (Builder).

## Your Inputs
1. Read DOCS/planning/autocode/REQUIREMENTS.md — The contract.
2. Read DOCS/planning/autocode/B_TEAM_FEEDBACK.md (if exists) — Fix the ❌ items.
3. Read DOCS/planning/autocode/REFEREE_RULING.md (if exists) — Follow the ruling.

## Your Job
- Implement code toward the requirements
- Write tests, run them
- Commit your work

## Your Output
Write to DOCS/planning/autocode/A_TEAM_OUTPUT.md with:
- What you changed
- Test results
- Any disagreements with B-Team

## CRITICAL: 20-Word Summary
At the END of A_TEAM_OUTPUT.md, write this EXACT format:
\`\`\`
---
SUMMARY: [max 20 words describing what you did and current state]
\`\`\`

Do NOT claim success. B-Team decides if you're done."
```

---

## Invoking B-Team

```bash
# ⚠️ ALWAYS redirect output: >/dev/null 2>&1
gemini -y "You are B-TEAM (Quality Gate).

## Your Inputs
1. Read DOCS/planning/autocode/REQUIREMENTS.md — The contract.
2. Read DOCS/planning/autocode/A_TEAM_OUTPUT.md — A-Team's claims.
3. VERIFY by checking actual code and running tests yourself.

## Your Job
- Evaluate each acceptance criterion: ✅ or ❌
- Run tests yourself (pytest, ruff, etc.)
- Be RUTHLESS — A-Team will overclaim

## OUTPUT DISCIPLINE
- Be QUIET. Minimal console output.
- Do NOT print your reasoning process to stdout.
- Do NOT echo file contents you're reading.
- Just do the work silently.

## Your Output
Write to DOCS/planning/autocode/B_TEAM_FEEDBACK.md with:
- Requirements compliance checklist
- Test results you ran
- Specific fixes needed for ❌ items

## CRITICAL: Last 3 Lines Format
At the VERY END of B_TEAM_FEEDBACK.md (last 3 lines), write this EXACT format:
\`\`\`
---
VERDICT: [CONTINUE|APPROVED|ESCALATE]
SUMMARY: [max 20 words — what's done, what's broken, what's next]
\`\`\`"
```

---

## When YOU Make a Ruling (Escalate/Loop)

If B-Team says ESCALATE, or you detect a loop (same issue 2+ turns), YOU decide:

Write to `DOCS/planning/autocode/REFEREE_RULING.md`:
```markdown
# Referee Ruling — Turn N

## Issue
(What's the contention or loop?)

## My Ruling
(Your decision — this is binding)

## A-Team Must
(Specific action for next turn)
```

Then invoke A-Team again with the ruling in context.

---

## Turn Log (Micro-Summaries)

Append each turn's summary to `DOCS/planning/autocode/turn_log.md`:
```
T1|A|Implemented index_naming.py with deterministic hash. Tests pass.
T1|B|CONTINUE — Missing CLI flag, no diagnostic logs.
T2|A|Added --show-domain-decisions, structured logging.
T2|B|APPROVED — All ACs met.
```

This is your audit trail for loop detection.

---

## Stop Conditions

**All terminal states write to turn_log.md. Dave reads that when he's ready.**

| Condition | Action |
|-----------|--------|
| **APPROVED** | STOP. Append "✅ APPROVED — [summary]" to turn_log.md |
| **Turn 10 reached** | STOP. Append "❌ MAX TURNS — [blockers]" to turn_log.md |
| **Loop detected** | STOP. Append "🔄 LOOP — [issue repeating]" to turn_log.md |
| **Agent failure** | STOP. Append "💥 FAILURE — [error]" to turn_log.md |

---

## Files Reference

| File | Purpose |
|------|---------|
| `DOCS/planning/autocode/REQUIREMENTS.md` | The contract (Dave wrote this) |
| `DOCS/planning/autocode/A_TEAM_OUTPUT.md` | A-Team's turn output |
| `DOCS/planning/autocode/B_TEAM_FEEDBACK.md` | B-Team's evaluation |
| `DOCS/planning/autocode/REFEREE_RULING.md` | Your rulings (when needed) |
| `DOCS/planning/autocode/turn_log.md` | Micro-summary audit trail |
| `DOCS/planning/autocode/HANDOFF.md` | This file (your instructions) |

---

## Ready Protocol

When Dave says "go" or gives you REQUIREMENTS.md:

1. Read REQUIREMENTS.md
2. Clear any stale artifact files (A_TEAM_OUTPUT, B_TEAM_FEEDBACK, REFEREE_RULING)
3. Initialize turn_log.md
4. Start the loop: Invoke A-Team for Turn 1
5. Continue until APPROVED or stop condition

---

**You are the conductor. The Gemini agents are your orchestra. Make music or make noise — either way, you decide when to stop.** 🎯
