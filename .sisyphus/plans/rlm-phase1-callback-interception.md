# RLM Phase 1: Callback Interception (AST, Nav Tools Only)

## Context

### Original Request
Enable RLM to call injected nav tools (`nav_outline`, `nav_ls`, `nav_read`, `nav_search`, `nav_info`) from model-generated Python when using the **process** sandbox backend, by implementing the Phase 1 design intent: **intercept tool calls outside the sandbox** (no IPC).

### Problem Summary
`llmc/rlm/sandbox/process_backend.py` injects **callback stubs** that raise at runtime:
- `llmc/rlm/sandbox/process_backend.py:226` (`_make_callback_stub`) raises RuntimeError for any callback call inside the worker process.

But `llmc/rlm/session.py` executes code blocks directly with `self.sandbox.execute(code)` (no interception layer):
- `llmc/rlm/session.py:345`..`llmc/rlm/session.py:372`

So the model can follow the prompt and call `nav_info()` but execution fails.

### Chosen Approach
Option 1: **AST-based interception in the orchestrator** (parent process) before calling `sandbox.execute()`.

- Supported tools (Phase 1): `nav_outline`, `nav_ls`, `nav_read`, `nav_search`, `nav_info`.
- Supported call form (Phase 1): **assignments only**
  - Allowed: `x = nav_info()`
  - Not allowed: `nav_info()` (bare), `print(nav_info())` (nested), `len(nav_ls("Foo"))` (nested), `a = b = nav_info()` (chained assign), tuple unpacking.
- `llm_query()` is **out of scope** for Phase 1 interception.

### Roadmap Note
Option 2 (full IPC callbacks) is explicitly deferred as "someday maybe" and should be moved to the back of the roadmap.

---

## Work Objectives

### Core Objective
Allow model-generated code to use nav_* tools in process sandbox by rewriting tool calls to injected values computed in the parent process.

### Concrete Deliverables
- New interception module implementing:
  - validation (reject unsupported patterns with actionable errors)
  - extraction of tool call sites
  - rewrite of code to remove direct tool calls
- RLMSession integration: intercept + execute tools + inject results + execute rewritten code.
- Prompt alignment: prompt teaches the assignment-only tool calling convention and does not advertise unsupported tools.
- Tests: unit tests for interceptor + session-level test validating `x = nav_info()` works end-to-end under process sandbox.

### Definition of Done
- `tests/rlm/test_sandbox.py` remains green.
- New tests for interception pass.
- A minimal session run can successfully execute a code block containing `x = nav_info()` without hitting the callback stub RuntimeError.

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **User wants tests**: YES (tests-after is acceptable, but interceptor code should be test-driven for safety)

### Required Commands
- `./.venv/bin/pytest tests/rlm/test_sandbox.py -q`
- `./.venv/bin/pytest tests/rlm -q`

---

## Design (SDD)

### Supported Syntax (Phase 1)
Only intercept tool calls where:
- Statement is `ast.Assign` with exactly 1 target
- Target is `ast.Name` (simple variable)
- RHS is `ast.Call` where `func` is `ast.Name` in the whitelist
- All args/kwargs are **literal constants** (via `ast.literal_eval`): strings, numbers, bool, None

Explicitly rejected patterns (return a clear error before sandbox execution):
- Bare calls: `nav_info()`
- Nested calls: `print(nav_info())`, `x = len(nav_ls("Foo"))`
- Tool calls inside comprehensions / lambdas / defs
- Non-literal args: `sym = "Foo"; x = nav_read(sym)`
- Multiple targets / destructuring / chained assignment

### Rewrite Strategy (Extract-Execute-Rebuild)
For each intercepted assignment:
1. Extract a `CallbackSite` (explicit dataclass):
   ```python
   @dataclass
   class CallbackSite:
       lineno: int
       col_offset: int
       target_name: str   # e.g. "x"
       tool_name: str     # e.g. "nav_info"
       args: list[Any]    # literal-evaluated positional args
       kwargs: dict[str, Any]  # literal-evaluated keyword args
   ```
2. Execute the tool in parent process using session's tool registry:
   - The `RLMSession` maintains `self.nav_tools: dict[str, Callable]` in the parent process
   - These are the actual nav_* implementations (not the sandbox stubs)
   - `value = self.nav_tools[tool_name](*args, **kwargs)`
3. Inject tool result into sandbox namespace under a collision-resistant name:
   - Pattern: `__rlm_icpt_{session_id[:8]}_{counter}` (e.g. `__rlm_icpt_7f3a2b1c_0`)
   - Counter is **session-scoped** to support multi-block execution
   - Must be picklable (process boundary). Nav tools return dict/list/str.
   - **Size guard**: If serialized result > 1MB, truncate with warning in feedback.
4. Rewrite the AST assignment RHS from `tool_call(...)` to `Name('__rlm_icpt_...')`.
5. Unparse rewritten AST back to code and pass to `sandbox.execute()`.
   - **Requires Python 3.9+** for `ast.unparse()`. Verify in pyproject.toml.

Ordering:
- Execute tool calls in source order (top-to-bottom within a block).

Error strategy:
- Validation errors produce a synthetic `ExecutionResult`-equivalent failure path so the session loop feeds the error back to the model as structured feedback.
- Tool execution exceptions are captured and returned as a failure with:
  - line number
  - tool name
  - args preview
  - actionable hint (e.g., "call nav_ls() first to list symbols").

### Prompt Alignment
`llmc/rlm/prompts.py` currently advertises `llm_query()` and does not teach the assignment-only constraint.

Update prompt generation to:
- Add a short "Tool Calling Convention" section with explicit examples:
  - `info = nav_info()`
  - `methods = nav_ls("MyClass")`
  - `code = nav_read("MyClass.method")`
- If `llm_query` remains injected, explicitly mark as unavailable in process sandbox OR remove it from injected tools for process backend until Phase 1.2.
- **Inject dynamically**: Only add this section when `sandbox_backend == "process"` to avoid prompt bloat for other backends.

### Thread Safety Note
- RLM sessions are single-threaded per session instance.
- Injection counter is instance-scoped, no cross-session race condition.
- If future work adds concurrent sessions, ensure counter is session-local (already is via `session_id` prefix).

---

## TODOs

- [ ] 1. Implement AST validator/extractor for tool call sites

  **What to do**:
  - Create a new module for interception (suggested: `llmc/rlm/sandbox/intercept.py`).
  - Implement:
    - `extract_tool_calls(code: str, allowed: set[str]) -> (sites, errors)`
    - Validation rules per "Supported Syntax".
  - Return errors with line numbers and concrete fix examples.

  **Must NOT do**:
  - Do not attempt to evaluate arbitrary expressions.
  - Do not support nested tool calls or non-literal args.

  **Parallelizable**: YES

  **References**:
  - `llmc/rlm/session.py:345` - code blocks are executed here; interception must happen before sandbox execution.
  - `llmc/rlm/sandbox/process_backend.py:226` - callback stubs are the failure mode to avoid.
  - `llmc/rag/locator.py` - example of AST visitor style used elsewhere.

  **Acceptance Criteria**:
  - Unit tests cover:
    - accepts `x = nav_info()`
    - rejects bare `nav_info()` with clear message
    - rejects `print(nav_info())`
    - rejects `x = nav_read(sym)` (non-literal arg)
  - `./.venv/bin/pytest tests/rlm/test_callback_intercept.py -q` passes.


- [ ] 2. Implement AST rewrite + injection plan for sandbox execution

  **What to do**:
  - Implement a transformer that rewrites `x = nav_info()` to `x = __rlm_tool_0`.
  - Produce a list of `(injected_name, tool_name, args, kwargs, lineno)` in execution order.
  - Ensure rewritten code round-trips (parse/unparse/parse).

  **Must NOT do**:
  - Do not inline large literals into code; use injected namespace variables.

  **Parallelizable**: YES (with 1)

  **References**:
  - `llmc/rlm/sandbox/process_backend.py:165`..`llmc/rlm/sandbox/process_backend.py:176` - namespace is copied into worker; injected values must be picklable.

  **Acceptance Criteria**:
  - Rewritten code contains no `nav_*(` substrings for intercepted calls.
  - Unit tests verify rewrite output executes without hitting callback stub.


- [ ] 3. Wire interception into `RLMSession.run()` before `sandbox.execute()`

  **What to do**:
  - In `llmc/rlm/session.py` execution loop, before `self.sandbox.execute(code)`:
    - parse + validate + extract sites
    - execute tools using `self._injected_tools`
    - inject results into sandbox via `sandbox.inject_variable(name, value)`
    - execute rewritten code
  - Log trace events for:
    - `tool_intercepted` (counts, tool names)
    - `tool_exec_error` (tool name, lineno)

  **Must NOT do**:
  - Do not change process sandbox semantics (timeouts, FINAL handling).

  **Parallelizable**: NO (depends on 1,2)

  **References**:
  - `llmc/rlm/session.py:345`..`llmc/rlm/session.py:372` - add interception here.
  - `llmc/rlm/sandbox/process_backend.py:240` - inject_variable enforces picklability.
  - `llmc/rlm/sandbox/interface.py` - ExecutionResult shape; integrate errors into existing feedback path.

  **Acceptance Criteria**:
  - A code block containing:
    - `info = nav_info()`
    - `FINAL(info)`
    returns a successful session answer.
  - Failures return actionable errors in the structured feedback injected at `llmc/rlm/session.py:381`.


- [ ] 4. Update prompts to teach the calling convention and avoid advertising unsupported tools

  **What to do**:
  - Update `llmc/rlm/prompts.py` to include explicit examples requiring assignment.
  - Ensure `llm_query()` is not encouraged until it is supported.

  **Must NOT do**:
  - Do not bloat prompt with long few-shot examples.

  **Parallelizable**: YES

  **References**:
  - `llmc/rlm/prompts.py:34`..`llmc/rlm/prompts.py:45` - current workflow text.

  **Acceptance Criteria**:
  - Generated prompt includes: "Tool calls must be assigned to variables".
  - Prompt does not tell the model to use `llm_query()` unless implemented.


- [ ] 5. Add/adjust tests to validate interception end-to-end

  **What to do**:
  - Add a session-level test that uses a mocked root model response containing:
    ```python
    info = nav_info()
    FINAL(info)
    ```
    and asserts success.
  - Keep existing `tests/rlm/test_sandbox.py` unchanged except where needed.

  **Parallelizable**: YES

  **References**:
  - `tests/rlm/conftest.py` - existing fixtures for mocking LLM responses.
  - `tests/rlm/test_sandbox.py` - FINAL and process timeout behavior.

  **Acceptance Criteria**:
  - `./.venv/bin/pytest tests/rlm -q` passes locally.


- [ ] 6. Roadmap hygiene: park IPC callbacks as "someday maybe"

  **What to do**:
  - Update `DOCS/ROADMAP.md` to move the "Phase 1.2 IPC callbacks" concept to the back (lower priority / later milestone).
  - Keep this plan's Option 1 as the committed Phase 1 approach.

  **Parallelizable**: YES

  **References**:
  - `DOCS/ROADMAP.md` section "RLM Phase 1.2"

  **Acceptance Criteria**:
  - Roadmap clearly communicates Option 2 as deferred.


---

## Guardrails
- No support for `llm_query()` in Phase 1 (remove from prompt or clearly mark unsupported).
- No nested tool calls; no non-literal args.
- Do not change the process sandbox kill/timeout behavior or FINAL handling.
- Do not commit `.env` or API keys; ensure secrets stay out of git history.

---

## Start Work
Plan saved to `.sisyphus/plans/rlm-phase1-callback-interception.md`.
Run `/start-work` to begin execution.
