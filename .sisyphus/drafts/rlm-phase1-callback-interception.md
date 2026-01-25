# Draft: RLM Phase 1 Callback Interception

## Requirements (confirmed)
- Implement Phase 1 callback interception (Option 1) for process sandbox so injected tools like `nav_info()` / `nav_read()` can be used from model-generated Python.
- Treat this as mission-critical: no hacks; implement per design intent and/or document gaps explicitly.
- Keep Option 2 (full IPC callbacks) as a “someday maybe” item at the back of the roadmap.
- Scope choice: Phase 1 supports **nav tools only** (`nav_outline`, `nav_ls`, `nav_read`, `nav_search`, `nav_info`).
- Calling style: **assignments only** (e.g., `x = nav_info()`). Bare calls like `nav_info()` should fail with a helpful error.

## Technical Decisions
- Sandbox backend stays **process-based** (killable timeouts); therefore callbacks cannot be executed directly in worker.
- Implement **AST-based interception / rewrite** of callback call sites before sandbox execution.
- Interception MUST support the model’s natural calling style (not brittle, and should produce actionable feedback when unsupported patterns are used).
- Prompt/tool alignment: ensure system prompt does not encourage unsupported tool usage (e.g., avoid advertising `llm_query()` until it is supported).

## Research Findings
- Current code registers callbacks into process sandbox, but process sandbox injects stubs that raise RuntimeError when called directly (no IPC).
- `llmc/rlm/session.py` executes model code blocks via `self.sandbox.execute(code)` with no interception layer.
- `llmc/rlm/prompts.py` generates prompt listing injected tool names and encourages `llm_query()`.
- Existing AST utilities exist in RAG for parsing/visiting (`llmc/rag/locator.py`, `llmc/rag/schema.py`), but no existing AST rewriter / NodeTransformer in repo.
- TreeSitterNav tool return values are picklable (strings/lists/dicts): `llmc/rlm/nav/treesitter_nav.py:137`..`llmc/rlm/nav/treesitter_nav.py:261`.

## Plan
- Work plan + SDD written to `.sisyphus/plans/rlm-phase1-callback-interception.md`.

## Scope Boundaries
- INCLUDE: Callback interception sufficient for `TreeSitterNav` tool calls and `llm_query` as injected tools in RLMSession.
- EXCLUDE: Full IPC callback execution across process boundary (Phase 1.2/Option 2).

## Open Questions
- Which callbacks must Phase 1 support on day 1?
- Should we enforce a strict calling convention (e.g., only `NAME = tool_call(...)` assignments) or support bare expressions too?
- What is the required behavior when interception sees an unsupported pattern?

## Notes / Risks
- Secrets: user provided API keys in chat as “sandbox keys”. Plan should assume keys are NOT committed and `.env` is ignored.
