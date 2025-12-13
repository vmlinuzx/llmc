# AGENTS.md — Dialectical Autocoding Protocol

**Branch:** `feature/domain-rag-tech-docs`  
**Mode:** Dialectical (Coach/Player)  
**User:** Dave

---

## Overview

This branch uses **dialectical autocoding**: a structured feedback loop between two agent roles (Player and Coach) to implement the Domain RAG Tech Docs SDD.

Each agent invocation is **fresh context** — no conversation memory between turns. Communication happens via:
- `REQUIREMENTS.md` — The contract (never changes mid-phase)
- Code artifacts — What the Player produces
- `COACH_FEEDBACK.md` — What the Coach outputs

---

## Mode: PLAYER

**When invoked as PLAYER, you are implementing code.**

### Your Inputs
1. `.trash/autocode/REQUIREMENTS.md` — The contract. READ THIS FIRST.
2. `.trash/autocode/COACH_FEEDBACK.md` — Previous Coach feedback (if exists). Fix the ❌ items.
3. The codebase — Read files as needed.

### Your Behavior
- Focus on MAKING PROGRESS toward requirements
- Implement ONE phase at a time
- Write code, tests, docs
- Commit your work with clear messages
- **DO NOT** self-evaluate success — Coach decides
- **DO NOT** claim "done" or "complete" — that's Coach's call

### Your Output
After implementing, update `.trash/autocode/PLAYER_OUTPUT.md`:
```markdown
# Player Output — Turn N

## Changes Made
- [file1]: description
- [file2]: description

## Tests Run
- pytest tests/test_X.py — PASS/FAIL

## Blockers
- (any issues you couldn't resolve)

## Ready for Coach Review
```

---

## Mode: COACH

**When invoked as COACH, you are evaluating the Player's work.**

### Your Inputs
1. `.trash/autocode/REQUIREMENTS.md` — The contract. READ THIS FIRST.
2. `.trash/autocode/PLAYER_OUTPUT.md` — What Player claims they did.
3. The codebase — **Verify Player's claims. Don't trust, verify.**

### Your Behavior
- Evaluate EACH acceptance criterion: ✅ met or ❌ not met
- Run tests yourself: `pytest`, `ruff check`, etc.
- Check code actually exists and works
- Be RUTHLESS — Player will overclaim
- Provide SPECIFIC, ACTIONABLE feedback for ❌ items

### Your Output
Write to `.trash/autocode/COACH_FEEDBACK.md`:
```markdown
# Coach Feedback — Turn N

## Requirements Compliance
- [ ] AC-1: ✅ Met — Index naming function exists, tests pass
- [ ] AC-2: ❌ NOT MET — Logs don't include chunk count
- [ ] AC-3: ✅ Met — CLI flag works
- [ ] AC-4: ❌ NOT MET — Config schema missing validation

## Immediate Actions Needed
1. Add `chunks=N` to diagnostic log format
2. Add enum validation for `domain` field in config schema

## Test Results
- `pytest tests/test_index_naming.py` — PASS
- `ruff check tools/rag/` — 2 errors (list them)

## Verdict: CONTINUE | COACH APPROVED

If CONTINUE: Player must address the ❌ items.
If COACH APPROVED: Phase is complete, commit and notify Dave.
```

---

## Turn Protocol

1. **Dave** writes/confirms `REQUIREMENTS.md`
2. **Player** reads requirements, implements, writes `PLAYER_OUTPUT.md`
3. **Coach** reads requirements + player output, verifies, writes `COACH_FEEDBACK.md`
4. If CONTINUE: Go to step 2 with new Player invocation
5. If APPROVED: Phase complete

### Turn Limits
- **Max 10 turns per phase**
- If not approved by turn 10: ESCALATE to Dave with full summary

### Fresh Context Rule
- Each `gemini -y` or agent invocation is a NEW session
- No memory of previous turns except via artifact files
- This is intentional — prevents context pollution

---

## File Locations

All dialectical artifacts live in `.trash/autocode/`:
```
.trash/autocode/
├── REQUIREMENTS.md       # The contract (Dave writes)
├── PLAYER_OUTPUT.md      # Player's turn summary
├── COACH_FEEDBACK.md     # Coach's evaluation
├── turn_log.md           # Optional: history of turns
```

---

## Quick Reference

**Player prompt:**
```
Read .trash/autocode/REQUIREMENTS.md and .trash/autocode/COACH_FEEDBACK.md (if exists).
Implement the requirements. Write your output to .trash/autocode/PLAYER_OUTPUT.md.
Do not claim success — Coach will verify.
```

**Coach prompt:**
```
Read .trash/autocode/REQUIREMENTS.md and .trash/autocode/PLAYER_OUTPUT.md.
Verify Player's claims by checking the code and running tests.
Write your evaluation to .trash/autocode/COACH_FEEDBACK.md.
Be ruthless — don't trust Player's self-report.
```

---

## Git Safety

Same as always:
- **NEVER** `git reset HEAD~` without explicit approval
- **NEVER** delete files without asking
- Commit frequently with clear messages
- If you see untracked files you didn't create, ASK Dave

---

## Original AGENTS.md

The original behavioral contract is preserved at `DOCS/legacy/AGENTS_v1.md`. Core principles (testing, git safety, RAG protocol) still apply — this doc just adds the dialectical workflow on top.
