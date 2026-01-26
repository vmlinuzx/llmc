# LLMC Custom Workflows

This document describes LLMC-specific custom commands and agents built on top of OhMyOpenCode.

---

## /llmc-sdd-generate: Automated SDD → Plan Pipeline

**Purpose**: Automate the Software Design Document (SDD) → Dependency Analysis → Work Plan generation pipeline with optional dialectical reviews.

**Location**: `.opencode/command/llmc-sdd-generate.md`

### Usage

```bash
/llmc-sdd-generate "Add JWT authentication to the API"
/llmc-sdd-generate "Implement real-time WebSocket notifications" --momus
/llmc-sdd-generate "Refactor config surface for type safety" --momus --auto-start
/llmc-sdd-generate "Add caching layer to database queries" --no-socrates --auto-start
```

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--momus` | OFF | Enable Momus review loop for the generated work plan (adds QA step) |
| `--auto-start` | OFF | Automatically invoke `/start-work {plan}` after completion |
| `--no-socrates` | OFF | Skip llmc-socrates SDD review (use for speed, not recommended) |

### Workflow Phases

```
┌─────────────────────────────────────────────────────────┐
│ PHASE 1: SDD Creation                                   │
├─────────────────────────────────────────────────────────┤
│ 1. Oracle → Create SDD (.sisyphus/sdds/SDD_{slug}.md)  │
│ 2. llmc-socrates → Review SDD (dialectical, optional)   │
│    - Max 3 iterations                                    │
│    - VERDICT: APPROVED | WITH CONCERNS | REQUIRE REV.   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PHASE 2: Dependency Analysis                            │
├─────────────────────────────────────────────────────────┤
│ 3. Oracle → Dependency graph, parallelizable clusters   │
│    Output: .sisyphus/analysis/DEPS_{slug}.md            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PHASE 3: Work Planning                                  │
├─────────────────────────────────────────────────────────┤
│ 4. Prometheus → Generate work plan from SDD + deps      │
│    Output: .sisyphus/plans/{slug}.md                    │
│ 5. Momus → Review plan (optional, if --momus flag)      │
│    - Max 3 iterations                                    │
│    - VERDICT: OKAY | REJECT                              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PHASE 4: Execution (Optional)                           │
├─────────────────────────────────────────────────────────┤
│ 6. /start-work {slug} (if --auto-start flag)            │
└─────────────────────────────────────────────────────────┘
```

### Output Artifacts

All artifacts are stored under `.sisyphus/`:

```
.sisyphus/
├── sdds/
│   └── SDD_{slug}.md          # Software Design Document
├── analysis/
│   └── DEPS_{slug}.md         # Dependency analysis
└── plans/
    └── {slug}.md              # Work plan (Prometheus format)
```

**Slug generation**: Feature request → kebab-case → truncate to 60 chars → append `_2`, `_3` if collision

**Example**:
- Request: "Add JWT authentication to the API"
- Slug: `add-jwt-authentication-to-the-api`
- Files:
  - `.sisyphus/sdds/SDD_add-jwt-authentication-to-the-api.md`
  - `.sisyphus/analysis/DEPS_add-jwt-authentication-to-the-api.md`
  - `.sisyphus/plans/add-jwt-authentication-to-the-api.md`

### Error Recovery

If a phase fails, the command stops and reports:
- Which phase failed
- Error message
- Which artifacts exist (partial completion)
- How to resume

**Example**:
```
❌ PHASE 2 FAILED: SDD Review Loop

Error: llmc-socrates found 2 blockers after 3 iterations

Artifacts Created:
- SDD: .sisyphus/sdds/SDD_add-jwt-auth.md (needs revision)

How to Resume:
1. Manually review and fix the SDD
2. Re-run: /llmc-sdd-generate "Add JWT authentication" --no-socrates
```

### When to Use Each Flag

| Scenario | Recommended Flags |
|----------|-------------------|
| **Quick prototyping** | (none) - fastest, Oracle-only SDD |
| **Production feature** | `--momus` - add plan QA |
| **Critical changes** | (default) - includes llmc-socrates SDD review |
| **Immediate execution** | `--auto-start` - hands off to /start-work |
| **Speed over quality** | `--no-socrates` - skip SDD review (not recommended) |

---

## llmc-socrates: SDD Review Agent

**Purpose**: Dialectical Software Design Document reviewer using the Socratic method.

**Location**: `.claude/agents/llmc-socrates.md`

### Role

llmc-socrates reviews SDDs for:
1. **Design Soundness** - Are decisions justified?
2. **Architectural Consistency** - Does this fit existing patterns?
3. **Completeness** - Are edge cases addressed?
4. **Implementability** - Can this be built mechanically?
5. **Risk Analysis** - Are migration paths documented?

### Key Constraint

**llmc-socrates respects the implementation direction.** It reviews whether the design is sound and complete, NOT whether it's the "best" approach.

**Will NOT reject because**:
- You disagree with the technology choice
- You think a different architecture would be better
- The approach seems unusual

**WILL reject (BLOCKER) if**:
- Core design decision is unjustified
- Solution doesn't address the stated problem
- Critical edge case is unaddressed
- Error handling strategy is missing

### Usage

llmc-socrates is invoked automatically by `/llmc-sdd-generate` (unless `--no-socrates` flag is used).

**Manual invocation** (for testing):
```typescript
delegate_task(
  subagent_type="llmc-socrates",
  run_in_background=false,
  load_skills=[],
  prompt="Review the SDD at: .sisyphus/sdds/SDD_my-feature.md"
)
```

### Output Format

```
VERDICT: [APPROVED | APPROVED WITH CONCERNS | REQUIRE REVISION]

## Design Soundness
✅ PASS
Design decisions are well-justified with clear rationale.

## Architectural Consistency
✅ PASS
Follows existing module structure and naming conventions.

## Completeness
⚠️ CONCERN
Edge case handling for API timeout not documented.

## Implementability
✅ PASS
File modifications are specific with clear function signatures.

## Risk Analysis
✅ PASS
Migration path and rollback strategy documented.

## BLOCKERS
(none)

## CONCERNS
- Document how the system handles API timeouts in Section 5

## Dialectical Questions Explored
- Q: Why REST API instead of GraphQL for this use case?
  A: SDD justifies based on existing infrastructure and team expertise.
```

---

## Naming Convention

All LLMC custom agents use the `llmc-` prefix to avoid collisions with OhMyOpenCode built-ins or global agents.

**Examples**:
- `llmc-socrates` (SDD reviewer)
- Future: `llmc-{agent-name}` for any new custom agents

---

## Integration with OhMyOpenCode

### Commands
- `.opencode/command/*.md` - Project-local custom commands
- Discovered automatically on session start
- Invoked via `/command-name` syntax

### Agents
- `.claude/agents/*.md` - Project-local custom agents
- Loaded automatically on session start
- Invoked via `delegate_task(subagent_type="agent-name")`

### Artifacts
- `.sisyphus/sdds/` - Software Design Documents
- `.sisyphus/analysis/` - Dependency analyses
- `.sisyphus/plans/` - Work plans (Prometheus format)

---

## Quick Reference

| Action | Command |
|--------|---------|
| Generate SDD + plan | `/llmc-sdd-generate "Feature description"` |
| With plan review | `/llmc-sdd-generate "Feature" --momus` |
| Skip SDD review | `/llmc-sdd-generate "Feature" --no-socrates` |
| Auto-execute | `/llmc-sdd-generate "Feature" --auto-start` |
| Full pipeline | `/llmc-sdd-generate "Feature" --momus --auto-start` |
| View command | `/llmc-sdd-generate` (no args) |

---

## Tips

1. **Be specific in feature requests**: "Add JWT authentication with refresh tokens" is better than "Add auth"
2. **Review artifacts before auto-start**: Even with `--momus`, manually check `.sisyphus/plans/{slug}.md` before execution
3. **Use --momus for production**: The extra Momus review catches plan-level issues llmc-socrates might miss
4. **Don't skip llmc-socrates**: The SDD review saves time by catching design issues early
5. **Check collision suffixes**: If you see `_2` or `_3`, you're regenerating an existing SDD - intentional?

---

## Troubleshooting

### Command not found
- **Cause**: Fresh session needed
- **Fix**: Restart OpenCode session or reload plugin

### Agent not invokable
- **Cause**: Agent file not loaded
- **Fix**: Check `.claude/agents/llmc-socrates.md` exists, restart session

### Review loops timeout
- **Cause**: Oracle/llmc-socrates/Momus not resolving issues
- **Fix**: Manually review the artifact (SDD or plan), fix the blockers, use `--no-socrates` or skip `--momus` to bypass

### Artifacts already exist
- **Behavior**: Slug collision generates `_2` suffix automatically
- **Manual control**: Delete existing artifacts or rename them before running `/llmc-sdd-generate`

---

## See Also

- [TURNOVER_SDD_Generate_Workflow.md](../.sisyphus/plans/TURNOVER_SDD_Generate_Workflow.md) - Full design document
- [sdd-generate-workflow.md](../.sisyphus/plans/llmc-sdd-generate-workflow.md) - Implementation plan
- [OhMyOpenCode Docs](https://github.com/code-yeongyu/oh-my-opencode) - Plugin documentation
