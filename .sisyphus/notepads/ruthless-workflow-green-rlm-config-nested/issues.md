## [2026-01-26T20:15] Task 4: Security Hardening - DEFERRED

### Reason for Deferral
- Security hardening requires careful design decisions about:
  - What "restrictive" mode should actually block
  - How to validate paths in RLMSession without breaking existing workflows
  - Whether to move POC tests or convert them to regression tests
- These decisions should be made with user input, not autonomously
- The plan's guardrail: "Must not water down security by reclassifying vulnerabilities"

### Current State
- RLM defaults to `security_mode="permissive"`
- `RLMSession.load_context(Path)` reads files without allowlist checks
- Security POC tests confirm vulnerabilities exist

### Recommendation
- Defer Task 4 until user clarifies security requirements
- Proceed with Tasks 5-6 (ruff/mypy cleanup) which are mechanical and safe
- Return to Task 4 with user guidance

### Blocker Status
- NOT blocking the ruthless flow IF we can make ruff/mypy green
- The test suite can pass with security issues documented (POCs exist as warnings)
