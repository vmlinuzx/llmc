---
description: Send tasks to Jules AI agent via CLI
---

# Jules Protocol

Send well-scoped tasks to Jules using the `jules` CLI.

## When to Use
- Documentation validation
- Well-defined refactoring with clear acceptance criteria
- Adding tests for existing code
- CLI improvements with existing patterns to follow

## When NOT to Use
- Security-critical changes (keep in-house)
- Complex architectural decisions
- Tasks without clear pattern to follow

## Usage

### Create a new task
```bash
# From the repo directory
jules new "Task description with full context"
```

### Task description format
Include:
1. **Goal** - What we're trying to achieve
2. **Problem** - Why this needs to change
3. **Changes Required** - Specific files and modifications
4. **Reference Files** - Patterns to follow
5. **Tests** - Required test coverage
6. **Acceptance Criteria** - How to know it's done

### List sessions
```bash
jules remote list --session
```

### Check a session
```bash
jules remote list --session | grep <task-id>
```

### Pull completed work
```bash
# Just fetch
jules remote pull --session <id>

# Fetch and apply patch
jules remote pull --session <id> --apply

# Or teleport (clone + checkout + apply)
jules teleport <id>
```

## Current Active Sessions
Check with: `jules remote list --session`

## Reviewing "Awaiting User Feedback" Tasks

When a Jules task shows "Awaiting User Feedback" status, the **agent should review and apply it**:

1. Preview the changes: `jules remote pull --session <id>`
2. Review the diff output:
   - Does the code follow existing patterns?
   - Are the changes correct?
   - Does it match the acceptance criteria?
3. If acceptable, apply: `jules remote pull --session <id> --apply`
4. Stage, commit, and push the changes

**Do NOT ask the user to review** - this is the agent's responsibility.

## Tips
- Jules works best with clear, specific tasks
- Include reference files so it follows existing patterns
- Doc validation runs nightly via scheduled task
- Review changes carefully before merging

// turbo-all
