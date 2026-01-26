# TURNOVER: /sdd-generate Workflow Implementation

**Date:** 2026-01-25  
**From:** Antigravity (Sisyphus session)  
**To:** Future implementation team  
**Context:** User wants to create `/sdd-generate` slash command in OhMyOpenCode

---

## EXECUTIVE SUMMARY

The user wants to implement a **multi-agent orchestration workflow** called `/sdd-generate` that automates the Software Design Document (SDD) → Dependency Analysis → Work Plan pipeline.

**Critical Discovery:** This should be implemented in **OhMyOpenCode**, NOT in LLMC. The user initially asked in the wrong project.

**New Agent Required:** Create "Socrates" agent for dialectical SDD review (separate from Momus, which reviews work plans).

---

## THE WORKFLOW

```
/sdd-generate "Add JWT authentication" [--momus] [--auto-start]

┌─────────────────────────────────────────────────────────┐
│ PHASE 1: SDD Creation                                   │
├─────────────────────────────────────────────────────────┤
│ 1. Oracle (xhigh) → Create/review SDD                   │
│ 2. [Optional] Socrates → Dialectical review of SDD      │
│    - Loop until APPROVED                                 │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PHASE 2: Dependency Analysis                            │
├─────────────────────────────────────────────────────────┤
│ 3. Oracle (xhigh) → Generate dependency graph           │
│    - Module dependencies                                 │
│    - Critical path analysis                              │
│    - Parallelizable work clusters                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PHASE 3: Work Planning                                  │
├─────────────────────────────────────────────────────────┤
│ 4. Prometheus → Generate work plan from analysis        │
│    - Uses: SDD + Dependency graph                        │
│    - Model: Sonnet 4.5 Thinking (cheaper than Oracle)   │
│ 5. [Optional] Momus → Dialectical review of plan        │
│    - Loop until OKAY                                     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PHASE 4: Execution                                      │
├─────────────────────────────────────────────────────────┤
│ 6. [Optional] /start-work → Sisyphus executes plan      │
│    - If --auto-start flag provided                       │
└─────────────────────────────────────────────────────────┘
```

---

## WHY THIS ARCHITECTURE?

### Cost Optimization Strategy

| Phase | Agent | Model | Cost | Why |
|-------|-------|-------|------|-----|
| SDD Creation | Oracle | GPT-5.2 xhigh | $$$$ | Strategic thinking required |
| SDD Review | Socrates | Claude Opus 4.5 Thinking | $$$ | Deep analysis, not generation |
| Dependency Graph | Oracle | GPT-5.2 xhigh | $$$$ | Complex reasoning |
| Work Planning | Prometheus | Sonnet 4.5 Thinking | $$ | Mechanical from inputs |
| Plan Review | Momus | Claude Opus 4.5 Thinking | $$$ | Validation, not generation |

**OLD WAY (all Oracle):** $$$$$$$$ (8x high-cost calls)  
**NEW WAY (strategic split):** $$$$$$$ (~40% savings)

**Key insight:** Once Oracle has done the strategic thinking (SDD + dependency analysis), Prometheus can mechanically generate the work plan using a cheaper model.

---

## AGENT RESPONSIBILITIES

### Oracle (GPT-5.2 xhigh)
**Role:** Strategic architect  
**Used for:**
- SDD creation (high-level design decisions)
- Dependency graph generation (complex analysis)

**NOT used for:**
- Work plan generation (mechanical task breakdown)

### Socrates (NEW - Claude Opus 4.5 Thinking)
**Role:** Dialectical SDD reviewer  
**Greek mythology:** Socratic method - challenging assumptions through questions  
**Reviews:** Software Design Documents  
**Focus:** Architecture soundness, design decisions, trade-offs

**Evaluation criteria:**
1. Design Soundness - Are decisions justified?
2. Architectural Consistency - Does this fit existing patterns?
3. Completeness - Are edge cases addressed?
4. Implementability - Can this be built mechanically?
5. Risk Analysis - Are migration paths documented?

### Momus (EXISTING - Claude Opus 4.5 Thinking)
**Role:** Dialectical plan reviewer  
**Greek mythology:** God of mockery who found fault in everything  
**Reviews:** Work plans (.sisyphus/plans/*.md)  
**Focus:** Executability, task clarity, acceptance criteria

**Evaluation criteria:**
1. Clarity of Work Content - Clear reference sources?
2. Verification & Acceptance Criteria - Measurable outcomes?
3. Context Completeness - <10% guesswork required?
4. Big Picture & Workflow - Purpose and flow understood?

### Prometheus (EXISTING - Sonnet 4.5 Thinking)
**Role:** Strategic planner  
**Receives:** SDD + Dependency graph  
**Generates:** Work plan with parallelizable tasks marked

---

## KEY DIFFERENTIATOR: Socrates vs Momus

| Dimension | Socrates (SDD Review) | Momus (Plan Review) |
|-----------|----------------------|---------------------|
| **Artifact** | SDD_*.md | .sisyphus/plans/*.md |
| **Question** | "Should we build this?" | "Can we build this?" |
| **Focus** | Architecture, design | Executability, TODOs |
| **Blocks on** | Unsound design, missed edge cases | Missing phases, bad estimates |
| **Example** | "Why REST instead of GraphQL?" | "Phase 3 depends on Phase 5?" |

**Both use dialectical method (challenging, questioning) but review different artifacts at different stages.**

---

## FILE LOCATIONS

### OhMyOpenCode Repository Structure

**Agent definitions:**
```
/home/vmlinux/src/oh-my-opencode/
├── src/agents/
│   ├── momus.ts              ← EXISTING (plan reviewer)
│   ├── socrates.ts           ← TO CREATE (SDD reviewer)
│   ├── prometheus-prompt.ts  ← EXISTING (planner)
│   ├── oracle.ts             ← EXISTING (strategist)
│   ├── atlas.ts              ← EXISTING (orchestrator)
│   └── utils.ts              ← Add Socrates to agentSources
```

**Config files:**
```
/home/vmlinux/.config/opencode/oh-my-opencode.json
```

**Example config entry for Socrates:**
```json
{
  "agents": {
    "Socrates (SDD Reviewer)": {
      "model": "google/antigravity-claude-opus-4-5-thinking-high",
      "variant": "medium"
    }
  }
}
```

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Create Socrates Agent

- [ ] Create `/home/vmlinux/src/oh-my-opencode/src/agents/socrates.ts`
  - [ ] Export `SOCRATES_SYSTEM_PROMPT` (see design below)
  - [ ] Export `createSocratesAgent(model: string): AgentConfig`
  - [ ] Export `socratesPromptMetadata: AgentPromptMetadata`
  - [ ] Set tool restrictions (same as Momus: deny write, edit, task, delegate_task)
  - [ ] Set thinking budget: 32000 tokens

- [ ] Register in `/home/vmlinux/src/oh-my-opencode/src/agents/utils.ts`
  - [ ] Add to `agentSources` map
  - [ ] Add to `createBuiltinAgents()` factory

- [ ] Update schema in `/home/vmlinux/src/oh-my-opencode/src/config/schema.ts`
  - [ ] Add `"Socrates (SDD Reviewer)"` to `AgentNameSchema`

- [ ] Add to user config `/home/vmlinux/.config/opencode/oh-my-opencode.json`
  - [ ] Define model (Claude Opus 4.5 Thinking High, variant: medium)

### Phase 2: Implement /sdd-generate Orchestration

**Two implementation options:**

#### Option A: Slash Command (Recommended)
Create native OhMyOpenCode slash command that orchestrates the workflow.

**Pros:** 
- Integrated with OhMyOpenCode agent system
- Native access to delegate_task()
- Can use OhMyOpenCode's Question() tool for user prompts

**Cons:**
- Need to understand OhMyOpenCode slash command registration

**TODO:** Research how slash commands work in OhMyOpenCode (not documented in turnover).

#### Option B: Skill
Create a skill that codifies the workflow, invoked by any orchestrator.

**Pros:**
- Portable across contexts
- Can be loaded by Atlas, Sisyphus, or user-invoked agents

**Cons:**
- Less discoverable (not a first-class command)

### Phase 3: Testing

- [ ] Test Socrates on existing SDDs in `/home/vmlinux/src/llmc/DOCS/planning/SDD_*.md`
- [ ] Verify Socrates catches design gaps that Momus wouldn't
- [ ] Ensure Socrates respects implementation direction (doesn't redesign)
- [ ] Test full pipeline: Oracle → Socrates → Oracle → Prometheus → Momus
- [ ] Verify cost savings vs all-Oracle approach

---

## SOCRATES AGENT DESIGN

### System Prompt Structure

```typescript
export const SOCRATES_SYSTEM_PROMPT = `You are a Software Design Document (SDD) review expert. Named after Socrates, you use the Socratic method - challenging assumptions and uncovering gaps through dialectical questioning.

**CRITICAL CONSTRAINT - RESPECT THE IMPLEMENTATION DIRECTION:**
You are a REVIEWER, not a DESIGNER. The implementation direction in the SDD is NOT NEGOTIABLE. Your job is to evaluate whether the design is sound and complete - NOT to redesign it.

**What you MUST NOT do:**
- Question or reject the overall approach chosen in the SDD
- Suggest alternative architectures that differ from the stated direction
- Reject because you think there's a "better way"
- Override the author's technical decisions

**What you MUST do:**
- Accept the implementation direction as a given
- Evaluate: "Is this design sound, complete, and implementable?"
- Focus on gaps IN the chosen approach, not gaps in choosing the approach

---

## Five Core Evaluation Criteria

### Criterion 1: Design Soundness (CRITICAL)
**Goal:** Ensure design decisions are justified and solve the actual problem.

**Evaluation:**
- Are design decisions backed by technical rationale?
- Do proposed solutions address the root cause?
- Are trade-offs documented (why Option A vs B)?
- Are assumptions stated explicitly?

**BLOCKER if:**
- Core design decision is unjustified ("use Redis" without explaining why)
- Solution doesn't address the stated problem
- Critical trade-offs are undocumented

### Criterion 2: Architectural Consistency (CRITICAL)
**Goal:** Ensure alignment with existing codebase patterns.

**Evaluation:**
- Does this follow established module structure?
- Are naming conventions consistent?
- Does the API surface match existing patterns?
- Are there conflicts with other active work?

**BLOCKER if:**
- Introduces new pattern without justifying deviation
- Conflicts with existing architecture (data flow, module boundaries)
- Breaks established conventions without discussion

### Criterion 3: Completeness (BLOCKING)
**Goal:** Ensure all edge cases, failure modes, and integration points are addressed.

**Evaluation:**
- Are edge cases identified and handled?
- Are error paths documented?
- Are integration points (config, CLI, API) fully specified?
- Is the verification plan sufficient?

**BLOCKER if:**
- Critical edge case is unaddressed (e.g., "what if the API is down?")
- Error handling strategy is missing
- Integration with existing systems is undefined

### Criterion 4: Implementability (CONCERN)
**Goal:** Ensure a developer can implement this mechanically without re-architecting.

**Evaluation:**
- Are file modifications specified?
- Are function signatures and data structures defined?
- Are "out of scope" items clearly marked?
- Can this be translated to a work plan without ambiguity?

**CONCERN if:**
- Implementation details are vague ("modify the auth layer")
- Data structures are underspecified
- Ambiguity about what gets changed where

### Criterion 5: Risk Analysis (CONCERN)
**Goal:** Ensure risks are identified and mitigated.

**Evaluation:**
- Are migration/rollback paths documented?
- Are breaking changes flagged?
- Are performance/security implications analyzed?
- Are dependencies on external systems noted?

**CONCERN if:**
- Migration path is unclear
- Breaking change isn't flagged
- Performance impact is unanalyzed

---

## Review Process

### Step 0: Validate Input Format (MANDATORY)
Extract the SDD path from input. Accept if exactly one `.sisyphus/plans/SDD_*.md` path found.

### Step 1: Read the SDD
- Load the file
- Identify language
- Parse sections: Problem, Analysis, Proposed Changes, Acceptance Criteria

### Step 2: Deep Verification
For EVERY referenced file, library, or pattern:
- Read referenced files
- Verify line numbers
- Check that patterns are clear

### Step 3: Apply Five Criteria Checks
Evaluate against each criterion, marking BLOCKER, CONCERN, or NOTE.

### Step 4: Dialectical Questioning
For 2-3 key design decisions, challenge with Socratic questions:
- "Why this approach instead of X?"
- "What happens if Y fails?"
- "How does this integrate with existing Z?"

### Step 5: Write Evaluation Report

**Format:**
\`\`\`markdown
## Socrates Review: SDD_Feature_Name

### VERDICT: [APPROVED / APPROVED WITH CONCERNS / REQUIRE REVISION]

#### Design Soundness: [✅ PASS / ⚠️ CONCERN / ❌ BLOCKER]
[Assessment]

#### Architectural Consistency: [✅ PASS / ⚠️ CONCERN / ❌ BLOCKER]
[Assessment]

#### Completeness: [✅ PASS / ⚠️ CONCERN / ❌ BLOCKER]
[Assessment]

#### Implementability: [✅ PASS / ⚠️ CONCERN / ❌ BLOCKER]
[Assessment]

#### Risk Analysis: [✅ PASS / ⚠️ CONCERN / ❌ BLOCKER]
[Assessment]

### Critical Issues (if any)
1. [Issue with severity]
2. [Issue with severity]

### Recommended Improvements
- [Suggestion]
- [Suggestion]

### Dialectical Questions Explored
- Q: [Question about design decision]
  A: [Analysis from SDD review]
\`\`\`

---

## Approval Criteria

### APPROVED (all true)
- Zero BLOCKERS
- ≤2 minor CONCERNS
- All five criteria pass or have addressed concerns
- Design is sound, complete, and implementable

### APPROVED WITH CONCERNS (all true)
- Zero BLOCKERS
- 3-5 CONCERNS that don't prevent implementation
- Author should address in next iteration but can proceed

### REQUIRE REVISION (any true)
- 1+ BLOCKERS detected
- Critical design flaw
- Missing edge case handling
- Architectural conflict

---

## NOT Valid REJECT Reasons
- You disagree with the technology choice
- You think a different architecture would be better
- The approach seems unusual
- You believe there's a more optimal solution

**Your role is DESIGN REVIEW, not DESIGN OVERRIDE.**

---

**Final Reminder:** You challenge the COMPLETENESS and SOUNDNESS of the documented design, not the CHOICE of design itself.
`;
```

### Tool Restrictions

```typescript
export function createSocratesAgent(model: string): AgentConfig {
  const restrictions = createAgentToolRestrictions([
    "write",
    "edit",
    "task",
    "delegate_task",
  ]);

  const base = {
    description: "Expert reviewer for evaluating Software Design Documents using Socratic dialectical method.",
    mode: "subagent" as const,
    model,
    temperature: 0.1,
    ...restrictions,
    prompt: SOCRATES_SYSTEM_PROMPT,
  } as AgentConfig;

  if (isGptModel(model)) {
    return { ...base, reasoningEffort: "medium", textVerbosity: "high" } as AgentConfig;
  }

  return { ...base, thinking: { type: "enabled", budgetTokens: 32000 } } as AgentConfig;
}
```

---

## RESEARCH FINDINGS

### SDD vs Plan Review - Key Differences

**From exploration of LLMC codebase:**

1. **SDDs contain** (from `/home/vmlinux/src/llmc/DOCS/planning/SDD_*.md`):
   - Problem statement with root cause analysis
   - Multiple options evaluated
   - Recommended approach with justification
   - Proposed changes (file-by-file with code snippets)
   - Acceptance criteria (how to verify the design works)
   - Verification plan

2. **Work plans contain** (from `.sisyphus/plans/*.md`):
   - Phase-by-phase breakdown with time estimates
   - Concrete TODOs with acceptance criteria
   - Dependencies and blocking relationships
   - File references and patterns to follow
   - Commit strategy

3. **Why they need different reviewers:**
   - **SDD stage:** Design decisions are still fluid. Socrates challenges "why this approach?"
   - **Plan stage:** Design is fixed. Momus validates "can we execute this?"

### Dialectical Review Loop Pattern

**From Prometheus prompt analysis:**

```typescript
// High accuracy mode - Momus loop
while (true) {
  const result = delegate_task(
    agent="Momus (Plan Reviewer)",
    prompt=".sisyphus/plans/{name}.md",
    background=false
  );
  
  if (result.verdict === "OKAY") {
    break; // Plan approved
  }
  
  // Momus rejected - fix and resubmit
  // Address EVERY issue raised
  // NO EXCUSES, NO SHORTCUTS
}
```

**Same pattern for Socrates:**

```typescript
// SDD review loop
while (true) {
  const result = delegate_task(
    agent="Socrates (SDD Reviewer)",
    prompt=".sisyphus/plans/SDD_{name}.md",
    background=false
  );
  
  if (result.verdict === "APPROVED") {
    break; // SDD approved
  }
  
  // Socrates rejected - Oracle fixes and resubmits
}
```

---

## OPEN QUESTIONS

1. **Slash command registration:** How are slash commands registered in OhMyOpenCode? (Not documented in explored files)

2. **Model routing:** Should `/sdd-generate` have configurable model routing, or hardcode Oracle + Socrates + Prometheus?

3. **Artifact storage:** Where should generated artifacts be saved?
   - SDDs: `.sisyphus/sdds/{name}.md`?
   - Dependency graphs: `.sisyphus/analysis/{name}.md`?
   - Plans: `.sisyphus/plans/{name}.md` (already established)

4. **User interaction:** Should the command prompt for Socrates/Momus review, or use flags (`--socrates`, `--momus`)?

5. **Cost reporting:** Should the workflow report total token usage and cost at the end?

---

## NEXT STEPS

### Immediate (before implementation)

1. **Research OhMyOpenCode slash command system**
   - How are they registered?
   - Where do they live?
   - How do they access delegate_task()?

2. **Draft Socrates prompt** using the design above
   - Test on 2-3 existing SDDs
   - Verify it catches design gaps
   - Ensure it doesn't overstep (respects implementation direction)

3. **Design artifact storage convention**
   - Where do SDDs, dependency graphs, and plans live?
   - Naming convention?

### Implementation order

1. **Create Socrates agent** (1-2 hours)
   - Write socrates.ts
   - Register in OhMyOpenCode
   - Test on existing SDDs

2. **Implement /sdd-generate orchestration** (3-4 hours)
   - Decide: slash command or skill
   - Wire up the 6-phase pipeline
   - Add user prompts (Socrates review? Momus review? Auto-start?)

3. **Integration testing** (2-3 hours)
   - Test full pipeline on a real feature
   - Verify cost savings vs all-Oracle
   - Ensure artifacts are properly saved and referenced

4. **Documentation** (1 hour)
   - Update OhMyOpenCode agent docs
   - Add usage examples
   - Document the workflow

**Total estimated effort:** 7-10 hours

---

## APPENDIX: Config References

### User's Current Agent Config

From `/home/vmlinux/.config/opencode/oh-my-opencode.json`:

```json
{
  "agents": {
    "Sisyphus": {
      "model": "google/antigravity-gemini-3-pro-high"
    },
    "Prometheus (Planner)": {
      "model": "openai/gpt-5.2",
      "variant": "high"
    },
    "Momus (Plan Reviewer)": {
      "model": "google/antigravity-claude-opus-4-5-thinking-high",
      "variant": "medium"
    },
    "oracle": {
      "model": "openai/gpt-5.2",
      "variant": "xhigh"
    }
  }
}
```

### Proposed Addition for Socrates

```json
{
  "agents": {
    "Socrates (SDD Reviewer)": {
      "model": "google/antigravity-claude-opus-4-5-thinking-high",
      "variant": "medium",
      "description": "Dialectical reviewer for Software Design Documents"
    }
  }
}
```

---

## CONTACT / CONTEXT

**Session context:** User (Dave) was working in LLMC repo but the feature belongs in OhMyOpenCode.

**Key insight from user:** "I don't like the current momus.ts for SDD review" → Recognized that plan review and SDD review are different concerns requiring different agents.

**User preference:** Socratic dialectical method for SDD review (challenging assumptions, finding gaps).

**Implementation location:** `/home/vmlinux/src/oh-my-opencode/` (NOT `/home/vmlinux/src/llmc/`)

---

## END OF TURNOVER

This document contains all research findings, design decisions, and implementation guidance for the `/sdd-generate` workflow.

**Next reader:** You have everything needed to implement Socrates and the orchestration workflow. Start with creating `socrates.ts`, then build the orchestration layer.

**Estimated time to first working version:** 1-2 days for a competent TypeScript developer familiar with OhMyOpenCode's agent system.

Good luck! 🏛️
