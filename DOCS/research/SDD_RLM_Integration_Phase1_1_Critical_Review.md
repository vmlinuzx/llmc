# Critical Review: SDD_RLM_Integration_Phase1.1 (LLMC)

This is a critical architecture + implementation review of the attached SDD. It focuses on:
- correctness vs the current LLMC repo structure
- security and safety of the execution model
- whether the "recursive" behavior is actually achieved
- practical, Phase-1-friendly changes that keep the design cheap, fast, and testable

---

## Executive verdict

The SDD is directionally strong (good decomposition: session / governance / nav / sandbox), but it has several **P0 blockers** that will cause implementation pain or incorrect behavior if you code it as-written:

1. **Repo integration mismatch**: it references modules that do not exist in the current LLMC tree (notably `llmc/chunking/*`). LLMC's tree-sitter lives under `llmc/rag/*` today.
2. **Budget enforcement is incomplete**: it enforces budgets for sub-calls but not for root calls, so you can still "accidentally spend $20" in one root loop.
3. **"Recursion depth" does not reflect real recursion** in the current design. It is tracking call nesting of `llm_query`, but the design does not create nested sessions/call trees in a way that matches the RLM paper's recursion concept.
4. **Thread-based timeouts are not actually stoppable** (Python threads cannot be killed safely). A timed-out code block can keep running forever.
5. **Prompts/tooling are inconsistent**: the system prompt advertises tools (e.g., `context_search`) that are not implemented.

Fixing these does not require abandoning the design. It requires aligning with LLMC's existing primitives and tightening the "governed execution" contract.

---

## What you got right (keep these)

### 1) Separation of concerns
- `session.py` orchestrates loop state
- `governance/` owns budgeting and policy decisions
- `sandbox/` encapsulates execution isolation (swapable backends)
- `nav/` avoids blind string slicing

This is exactly the right set of seams for Phase 1.

### 2) Financial circuit breakers
Moving from call-count limits to token/cost budgeting is the correct mental model.

### 3) Navigation as a first-class tool
The biggest real-world win in RLM-like systems is **not** recursion; it's **fast structural navigation** that prevents token waste and hallucinated exploration. Your instinct to build `TreeSitterNav` is correct.

---

## P0 blockers (must fix before implementation)

### P0.1 Incorrect assumptions about existing LLMC modules
The SDD claims it "leverages existing LLMC infrastructure" via `llmc/chunking/` and `llmc.chunking.treesitter` imports, but **that path does not exist in the current repo**.

**Reality in current LLMC repo:**
- tree-sitter parsing and language detection live in `llmc/rag/lang.py`
- structural skeletonization exists in `llmc/rag/skeleton.py`
- symbol/span extraction is in `llmc/rag/lang.py` + `llmc/rag/schema.py` (via `SpanRecord`)

**Actionable fix:**
- Update the design to build `TreeSitterNav` on top of **`llmc/rag/lang.py`** and (optionally) **`SpanRecord`**.
- Treat `Skeletonizer` as the Phase-1 baseline for `outline()`.

**Why this matters:**
If you implement `llmc/rlm/nav/treesitter_nav.py` as written, you'll immediately hit missing imports and end up duplicating existing code.

### P0.2 The sandbox timeout is not enforceable
`RestrictedPythonBackend.execute()` uses a thread with `thread.join(timeout=...)`. If the code times out, the thread keeps running. There is no safe kill.

**Concrete failure mode:**
- model writes `while True: pass`
- you hit timeout
- your process remains pegged (or worse: deadlocks, leaks memory) forever

**Actionable fix (cheap + effective):**
- Make the Tier-0 "dev sandbox" **process-based**, not thread-based.
- Use `multiprocessing` or `subprocess` to run code in a separate interpreter with:
  - a hard timeout (kill process)
  - resource limits (CPU, memory) if available
  - a narrow RPC interface for callbacks

This still keeps "Tier 1: wasm" as an option later, but it gives you a Phase-1 implementation that actually stops.

### P0.3 Budget enforcement applies only to sub-calls
The session loop records root-model usage, but it does **not reserve/check** budget *before* doing root calls. That means the session can exceed budget in the root call before governance can stop it.

**Actionable fix:**
- Wrap root calls in the same governance mechanism (reserve -> call -> record).
- If you want different policies, create:
  - `RootCallPolicy` (usually higher max_tokens, stricter turn cap)
  - `SubCallPolicy` (cheaper, smaller max_tokens, higher count)

### P0.4 "Recursion depth" does not represent recursion yet
The budget's `enter_recursion()` / `exit_recursion()` is invoked per sub-call. But your `llm_query()` bridge is a synchronous function that returns a string. This creates a *flat* sequence of subcalls rather than a recursive call tree.

In the RLM paper, recursion typically emerges as:
- LLM writes code that spawns sub-LLM calls on subproblems
- those subcalls produce artifacts that drive further decomposition
- deeper levels occur when a sub-LLM itself triggers structured subcalls (or when the system spawns nested sessions)

**Actionable fixes (pick one for Phase 1):**
1) **Rename the concept**: treat this as **subcall budget** not recursion depth (lowest risk; still useful).
2) Implement real recursion: allow sandbox code to call something like `spawn_session(prompt, context_ref)` that creates a nested RLMSession with bounded depth.

If you keep "depth" without real nesting, it will confuse debugging and give a false sense of safety.

### P0.5 Prompt/tool mismatch
The BASIC prompt documents `context_search(pattern)` but there is no such tool registered anywhere.

**Actionable fix:**
- Either implement `context_search()` and `context_slice()` as host callbacks, or remove them from prompt.
- Prompts must be mechanically aligned with injected callbacks, or the model will waste turns.

---

## P1 issues (high value improvements)

### P1.1 Bypassing LLMC's existing LiteLLM abstraction
`GovernanceMiddleware` and `RLMSession.run()` call `litellm.acompletion(...)` directly. LLMC already has a backend layer with config, param dropping, and error mapping (`llmc/backends/litellm_core.py`).

**Why you care:**
- You will duplicate error handling and drift from the repo's provider conventions.
- Budgeting and telemetry should be anchored at a single call surface.

**Actionable fix:**
- Route calls through a single adapter that wraps `LiteLLMCore` / `LiteLLMAgentBackend` (or introduce a `LiteLLMCallAdapter` used by governance).

### P1.2 Token counting is not provider-accurate
`tiktoken` is OpenAI-oriented. Falling back to `cl100k_base` for non-OpenAI models is usually wrong, sometimes badly wrong.

**Actionable fix:**
- In Phase 1, do conservative estimation (char/4) but apply a safety multiplier for non-OpenAI.
- Optionally, allow per-provider tokenizers later.
- Most importantly: **treat cost as policy, not truth** (because local models cost $0 but burn time).

### P1.3 Pricing table is hard-coded and will rot
`MODEL_PRICING` embedded in code becomes stale quickly.

**Actionable fix:**
- Move pricing into config (`llmc.toml`) and allow overrides.
- Treat "unknown model" as (a) blocked or (b) uses a configured default.

### P1.4 TreeSitterNav scope: define the minimum viable nav
The nav module is currently a conceptual API with a large TODO (`_build_index`). You need to define what it can do *in week 2* without building an IDE.

**MVP recommendation:**
- `outline()` implemented by reusing `llmc/rag/skeleton.py` (fast win)
- `read_symbol(symbol)` implemented by building a symbol map from `SpanRecord` extraction (python-first)
- `search_regex(pattern)` implemented over bytes (cheap)
- Leave AST query search for later

This avoids writing your own indexer in Phase 1.1.

### P1.5 Execution feedback loop is lossy
In `RLMSession.run()`:
- stderr handling is inconsistent (success path may ignore stderr)
- multi-code-block output is concatenated without structure
- there is no "tool result" schema fed back

**Actionable fix:**
Feed structured execution results back to the root model as JSON:
- `success`, `stdout_preview`, `stderr_preview`, `error`, `final_answer_present`
- include truncation metadata

This will reduce prompt drift and improve reproducibility.

---

## P2 issues (later, but note now)

### P2.1 Security posture is underspecified
The SDD correctly warns RestrictedPython is insecure. But it still designs the system around executing untrusted model code in-process during Phase 1.

**Phase 1 pragmatic position:**
- Assume trusted output, but still isolate with a process sandbox to avoid accidental footguns.
- If you want adversarial safety later: move to wasm or microVM.

### P2.2 Session persistence/resume is a major feature
The SDD lists it as Phase 2. That is correct. Just ensure the trace format is stable now so you can replay later.

### P2.3 Multi-file / repo-scale navigation is missing from nav design
Right now, TreeSitterNav accepts a single source string/path. RLM for repo understanding needs:
- listing files
- outlining file-level structure
- reading symbols across files

LLMC already maintains file inventories in RAG indexing; reuse that instead of re-inventing file discovery.

---

## Concrete alignment suggestions (LLMC-specific)

These are "drop-in" alignments to reduce work and reduce divergence:

1) **Use `llmc/rag/lang.py` for parsing and language detection**
   - Replace `detect_language`, `get_parser_for_language`, `parse_source` imports accordingly.

2) **Use `SpanRecord` as the nav index**
   - `SpanRecord` already tracks `symbol`, `kind`, `start_line/end_line`, byte ranges.
   - Build `nav_ls()` from span prefixes and `nav_read()` via `SpanRecord.read_source()`.

3) **Use `Skeletonizer` for `nav_outline()`**
   - It already produces a "header-file view" and it is cheap.

4) **Route model calls through LLMC backends**
   - Even if governance remains separate, anchor actual calls to one LLMC adapter.

---

## Testing strategy critique (and fixes)

### Problem: tests as written are not deterministic
Your integration tests call real models. That makes CI flaky and expensive.

**Actionable fix:**
- Mock the completion layer (LiteLLM adapter) and supply canned responses:
  - response with code block
  - response with FINAL call
  - response with no code (to test nudge behavior)
  - error cases

### Problem: unit tests include bugs
Example issues:
- `code = "class Big:\n" + "    def m{i}(self): pass\n" * 100` never formats `{i}`
- `test_soft_limit_callback` likely exceeds budget rather than warning depending on pricing assumptions

**Actionable fix:**
Treat the SDD tests as intent sketches, not literal. Convert them to deterministic tests with a fake backend and known token usage.

---

## Recommended minimal change set (what I'd do before coding)

If you want Phase 1.1 to land fast and not destabilize LLMC:

1) Replace thread sandbox with process sandbox for Tier 0 (dev)
2) Enforce budget for root calls and subcalls consistently
3) Rename or implement actual recursion semantics (avoid misleading "depth")
4) Implement `nav_outline` via `Skeletonizer` and `nav_read` via `SpanRecord`
5) Make prompts perfectly match injected callbacks
6) Use LLMC backend adapter as the single LLM call surface (do not call litellm directly from multiple places)

---

## Closing note

This SDD is close to a shippable Phase-1 plan, but right now it is "architecturally correct, repo-inconsistent". Fix the integration points first, otherwise implementation will devolve into emergency rewrites inside `nav/` and `sandbox/`.
