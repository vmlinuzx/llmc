# Review: SDD_RLM_MCP_Integration_1Z

> **Source:** DOCS/planning/SDD_RLM_MCP_Integration_1Z.md  
> **Date:** 2026-01-25  
> **Reviewer:** Dialectical synthesis of internal feedback

---

## Summary

The SDD is well-structured and clearly specifies the happy-path implementation. However, it has significant gaps in **trust boundary specification**, **failure mode handling**, and **verification rigor**. The security section makes unsubstantiated claims that need enforcement or removal.

### Context Update (from user)

- This feature will be used in a hospital environment, with **local inference** expected there.
- This is not hospital-only; user also intends to use **large cloud LLMs** heavily in other contexts.
  - Implication: the SDD should explicitly specify an **egress policy** (local-only vs allow-remote) and how it is selected/configured.

### Confirmed decision

- `model` override should exist as an option, but be **disabled by default** (`allow_model_override = false`).

### Publishing decision

- Publish the revised SDD as a new v2 file (keep the original SDD for history).

---

## Critical Gaps

### 1. Trust Boundary Ambiguity

**Issue:** The SDD does not specify the deployment topology.

| Transport | Trust Model | Risk Level |
|-----------|-------------|------------|
| stdio (Claude Desktop) | Single-user, local | Low |
| HTTP/SSE daemon | Multi-user, network | **High** |

**Impact:** Security posture differs *radically* between these modes. The claim "no additional attack surface vs CLI" is only true for stdio.

**Action Required:** Add explicit transport scope to Section 6, or defer HTTP exposure to a future SDD with proper threat modeling.

---

### 2. Unenforceable Schema Constraints

**Issue:** The tool schema permits both `file_path` AND `context` to be submitted simultaneously. Mutual exclusion is enforced only in Python code.

```json
// Current: Both optional, no oneOf constraint
"file_path": {"type": "string"},
"context": {"type": "string"},
```

**Action Required:** Either:
- Use JSON Schema `oneOf` to enforce at schema level, or
- Document this as a known limitation with runtime validation as the enforcement point

---

### 3. Unsubstantiated Security Claims

**Issue:** Section 6 claims:
> "File paths validated against `allowed_roots` (if configured)"

**Research Finding:** No `allowed_roots` enforcement exists in the proposed `rlm_query()` function or in `RLMSession.load_code_context()`.

**Action Required:** Either:
- Implement `allowed_roots` validation in the handler, or
- Remove the claim and document this as out-of-scope

---

### 4. Missing Failure Mode Specifications

**Issue:** The SDD does not specify behavior for:

| Failure Mode | Expected Behavior? |
|--------------|-------------------|
| Provider timeout | ? |
| Budget exceeded mid-analysis | ? |
| Concurrent invocations | ? |
| Cancellation request | ? |
| Model unavailable | ? |

**Action Required:** Add a **Failure Modes** section specifying error responses for each case, or mark these as implementation-defined.

---

### 5. File Size Limits

**Issue:** `RLMSession.load_code_context()` has no file-size guard. A malicious or accidental multi-GB file could exhaust memory.

**Research Finding:** `load_context()` enforces `max_context_chars`, but file-path loading bypasses this.

**Action Required:** Either:
- Add file size check before loading (configurable limit), or
- Document max file size in acceptance criteria

---

### 6. Verification Plan Gaps

**Issue:** Unit tests cover input validation but lack:

- **Security tests:** Path traversal (`../../../etc/passwd`), symlink escape
- **Resilience tests:** Oversized files, provider errors, timeout behavior
- **Concurrency tests:** Parallel invocations

**Action Required:** Add test cases to Section 4 covering these vectors.

---

## Minor Improvements

### Path Resolution Clarity

The `file_path` description says "relative to repo root or absolute" but `repo_root` is not exposed to MCP clients. How does the client know what paths are valid?

**Suggestion:** Document that `repo_root` is set by server initialization and paths are resolved relative to it.

### Trace Privacy

RLM tracing (`trace_enabled`) can expose prompt/response content. The SDD disables it for MCP but should document this decision and rationale.

---

## Recommended SDD Updates

1. **Section 1:** Add deployment scope (stdio only for v1.Z)
2. **Section 3.1:** Note schema limitation re: mutual exclusion
3. **Section 6:** 
   - Remove `allowed_roots` claim (or implement it)
   - Add trust boundary bullet
   - Add file size limit bullet
4. **Section 4:** Add security/resilience test cases
5. **New Section 4.5:** Add failure modes table

---

## Open Questions for Author

1. Is HTTP/SSE exposure intended for 1.Z or deferred?
2. What is the maximum file size RLM should accept?
3. Should `allowed_roots` be implemented now or documented as future work?
4. Resolved: default `mcp.rlm.profile` should be `unrestricted`, with docs recommending `restricted` for hospital deployments.

---

## Verdict

**Conditional Approval** — The core design is sound. Address the unsubstantiated security claims and add failure mode specifications before implementation begins.
