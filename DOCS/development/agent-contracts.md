# Agent Contracts

This document outlines the expectations for AI agents (and human developers) working on the LLMC codebase.

## The Prime Directive

**Read `AGENTS.md` in the repository root.**

The `AGENTS.md` file is the authoritative source for:
- Behavioral protocols
- Coding standards
- Testing requirements
- Workflow rules

## Key Protocols

### 1. Ruthless Testing
- **Trust nothing.** Verify every change.
- **Fail loud.** Report failures immediately; do not suppress them.
- **No sleep.** Use deterministic waits, not `time.sleep()`.

### 2. Documentation First
- Update documentation *before* or *with* code changes.
- Follow the [Diátaxis](https://diataxis.fr/) framework (Tutorials, How-To, Reference, Explanation).

### 3. Security
- Use `llmc_mcp.tools.fs` for file operations to ensure path validation.
- Do not bypass isolation checks (`require_isolation`) without explicit approval.

## Agent Workflows

Common workflows are defined in `.agent/workflows/`:

- `doc-validation.md`: This workflow.
- `security-audit.md`: Protocol for security reviews.
- `ruthless-testing.md`: Protocol for rigorous testing.

## See Also

- [AGENTS.md](../../AGENTS.md)
- [CONTRACTS.md](../../CONTRACTS.md) (if available)
