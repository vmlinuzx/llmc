# Teaching Testing Agents About Design Decisions

## Problem
When Ren (or other testing agents) flags intentional design choices as bugs, it creates noise and wastes review time.

**Example:** Ren flagged `check=False` in `subprocess.run()` as a safety issue, when it was actually a deliberate choice for better error handling and logging.

## Solution: Multi-Layer Documentation

We've implemented a three-layer approach to help testing agents distinguish bugs from intentional design:

### 1. **Inline Code Comments** (Primary Defense)
```python
# NOTE: check=False is INTENTIONAL. We want explicit exit code handling (line 90)
# so we can log stderr on failure. Using check=True would raise CalledProcessError
# and prevent our detailed logging. See: design_decisions.md
result = subprocess.run(
    cmd,
    check=False,  # Explicit: we handle exit codes manually below
    ...
)
```

**Signals:**
- "INTENTIONAL" in CAPS
- Explains the "why"
- References design decisions doc for full context

### 2. **Design Decisions Document** (Reference Material)
Created `llmc/docgen/design_decisions.md` with structured entries:

```markdown
## DD-001: Explicit Exit Code Handling in Shell Backend

**File:** `llmc/docgen/backends/shell.py`  
**Date:** 2025-12-03  
**Status:** Active

### Decision
Use `check=False` in `subprocess.run()` and handle exit codes explicitly.

### Rationale
1. Better logging of stderr on failures
2. Granular error categorization (timeout vs execution vs exit code)
3. Specific error messages for debugging

### Testing Considerations
Testing tools should recognize this pattern as intentional defensive programming.
```

**Benefits:**
- Searchable by testing agents
- Provides full context and rationale
- Documents trade-offs
- Includes testing guidance

### 3. **Testing Agent Instructions** (Meta-Level)
Updated `tools/ren_rethless_testing_agent.sh`:

```markdown
- **Check design decisions**: Before flagging something as a bug, 
  check if there's a `design_decisions.md` or `DESIGN_DECISIONS.md` 
  file in the module. Intentional design choices with rationale 
  documented are NOT bugs.
```

**Effect:**
- Ren now knows to look for design decision docs
- Reduces false positives
- Encourages thoughtful analysis

## How It Works Together

### Testing Agent Workflow (Updated)
```
1. Agent finds suspicious pattern (e.g., check=False)
2. ↓
3. Checks inline comments → Sees "INTENTIONAL" and doc reference
4. ↓
5. Reads design_decisions.md → Understands rationale
6. ↓
7. Makes informed decision:
   - If design is sound: Skip the issue
   - If disagrees: Note it as "Questionable Design Decision" (not a bug)
   - If implementation doesn't match design: Flag as deviation bug
```

### Developer Workflow
```
1. Make non-obvious design choice
2. ↓
3. Add inline comment with "INTENTIONAL" + brief reason
4. ↓
5. Document in design_decisions.md with full context
6. ↓
7. Testing agents understand the choice
8. ↓
9. Future developers learn from the decision
```

## Example: The `check=False` Case

### Before Documentation
**Ren's Report:**
> Bug: Missing `check=True` in subprocess. Severity: High.

**Problem:** False positive, wasted review time

### After Documentation
**Ren's Analysis:**
1. Sees `check=False` in code
2. Reads inline comment: "INTENTIONAL - see design_decisions.md"
3. Checks DD-001 in design_decisions.md
4. Understands: Explicit handling provides better logging
5. **Decision:** Not a bug, intentional design for observability

**Result:** No false positive!

## Guidelines for Adding Design Decisions

### When to Document
Add a design decision when:
- ✅ Pattern deviates from common practice (e.g., not using `check=True`)
- ✅ Choice has non-obvious trade-offs
- ✅ Future reviewers might question the approach
- ✅ Linters/analyzers flag it as suspicious

Don't document:
- ❌ Standard patterns everyone recognizes
- ❌ Obvious choices with no alternatives
- ❌ Temporary hacks (fix or add TODO instead)

### Format
```markdown
## DD-XXX: [Short Title]
**File:** [File path]
**Date:** [YYYY-MM-DD]
**Status:** [Active|Superseded|Deprecated]

### Decision
[What was decided - one sentence]

### Context
[Why this decision was needed]

### Rationale
[Why this approach over alternatives]

### Consequences
[Trade-offs, implications, testing notes]
```

## Benefits

### For Testing Agents
- ✅ Fewer false positives
- ✅ Better understanding of codebase
- ✅ Can focus on real bugs
- ✅ Learn patterns to recognize

### For Developers
- ✅ Captures institutional knowledge
- ✅ Explains "why" not just "what"
- ✅ Reduces repetitive questions
- ✅ Helps onboarding

### For Reviewers
- ✅ Context for non-obvious choices
- ✅ Can challenge designs with full info
- ✅ No need to re-litigate old decisions

## Summary

**Problem Solved:** Testing agents now distinguish intentional design from bugs

**Implementation:**
1. Inline comments with "INTENTIONAL"
2. design_decisions.md for full context
3. Testing agent instructions updated

**Next Time:** When making a non-obvious choice, document it immediately. Future-Ren will thank you!

---

**Files Created:**
- `llmc/docgen/design_decisions.md` - Design decision registry
- `tests/REPORTS/teaching_testing_agents_design_decisions.md` - This document

**Files Modified:**
- `llmc/docgen/backends/shell.py` - Added inline comment
- `tools/ren_rethless_testing_agent.sh` - Added design decision check
