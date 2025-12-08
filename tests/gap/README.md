# Gap Analysis & Test Generation

This directory contains artifacts from Rem's Gap Analysis.

## Structure

- **SDDs/**: Software Design Documents describing missing tests.
- **REPORTS/**: After Action Reports summarizing analysis sessions.

## Workflow

1. **Analysis**: Rem finds a gap.
2. **Design**: Rem writes an SDD in `SDDs/`.
3. **Execution**: Rem spawns a sub-agent to implement the test defined in the SDD.
4. **Result**: New tests appear in `tests/` or `tests/security/`.
