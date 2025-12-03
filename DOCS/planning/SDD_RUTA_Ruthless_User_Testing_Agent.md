# Software Design Document - Ruthless User Testing Agent (RUTA)
**Version:** v1.0 - **Date:** 2025-12-03 - **Owner:** LLMC  
**Status:** Draft - Ready for Phase 1 Implementation

---

## 0. Executive Summary

The **Ruthless User Testing Agent (RUTA)** is a multi-agent testing harness for LLMC that behaves like a **simulated end user**, exercises the system through **real interfaces** (CLI, MCP/API, TUI, HTTP), and then **analyzes what happened**:

- Did the user actually achieve their goal?
- Did the system use the **right tools** (and do those tools work)?
- Did we violate any **expected properties**, such as "adding the word `model` to a search query must not drop results from 6,000 to 0"?
- Did the environment **lie** about its capabilities (for example, claiming Unix tools are available while `sed` is blocked)?

RUTA complements existing LLMC agents:

- **Security Testing Agent** - focuses on security posture and sandbox boundaries.
- **Ruthless System Testing Agent** - focuses on core functional tests and internal APIs.
- **Ruthless User Testing Agent (this SDD)** - focuses on **end-to-end user flows**, **tool usage correctness**, **capability alignment**, and **semantically weird failures** (like the `"model"` search bug).

The design uses concepts from **simulation-based agent testing**, **LLM application evaluation frameworks**, and **metamorphic testing for search/ML systems**: we express expectations as **properties/relations** rather than exact outputs, and we log and analyze traces to detect failures.

Implementation is broken into **phases**, each with a difficulty rating (1-10). Early phases are low-risk, low-effort building blocks; later phases add sophistication like metamorphic relations and auto-generated user scenarios.

---

## 1. Goals and Non-Goals

### 1.1 Goals

1. **Simulated User Flows**
   - Execute realistic user tasks (for example, "search for model selection docs", "trigger enrichment for repo X") via **only public interfaces** (CLI/TUI/MCP/API).
   - No cheating with internal hooks - same path a human would use.

2. **Tool Usage and Capability Validation**
   - Verify that agents:
     - Use **appropriate tools** (for example, RAG search, enrichment triggers, shell utilities) when available.
     - Avoid tools that are explicitly forbidden for a scenario.
   - Detect environment inconsistencies, such as a tool being "documented as available" but actually broken or blocked (for example, `sed` not found but Python is allowed).

3. **Property-Based and Metamorphic Testing for Search and Agents**
   - Formalize expectations as properties and metamorphic relations:
     - Example: for search, adding a common term should not make results drop to zero unless the term is highly restrictive.
   - Evaluate runs against these properties instead of brittle exact-match assertions.

4. **Rich Telemetry and Incident Reports**
   - Capture traces: prompts, tool calls, queries, responses, metrics (latency, error counts).
   - Summarize failures as **INCIDENT REPORTS** similar to the `"model"` bug example, suitable for human review, tickets, and regression tracking.

5. **CI-Friendly Test Harness**
   - Provide a CLI and programmatic API to:
     - Run single scenarios or suites.
     - Enforce quality gates (for example, "no P0 incidents allowed on main branch").

### 1.2 Non-Goals (for v1)

- **No automatic patching or remediation.**
  - RUTA reports issues; it does not change code.
- **No full fuzzing or RL-style optimization in v1.**
  - Scenario generation is bounded and mostly deterministic early on.
- **No external SaaS dependency.**
  - Design for local-first evaluation; take inspiration from existing LLM eval tooling, but execute inside LLMC.
- **No GUI dashboard initially.**
  - v1 outputs structured JSONL and markdown incident reports that can later be surfaced in any UI.

---

## 2. System Context

### 2.1 Environment

RUTA runs **inside the LLMC ecosystem**, alongside:

- **LLMC CLI/TUI** - primary user interaction surface.
- **MCP server(s)** - tools exposed via Model Context Protocol.
- **TE (Tool Envelope)** - wrapping heavy operations (search, enrichment, code execution) with telemetry, progressive disclosure, and so on.
- **RAG/Search Engine** - backing search indices and content retrieval for code and docs.
- **Security and Ruthless Testing Agents** - existing testing agents, focused on different aspects.

RUTA consumes **the same tools and interfaces** LLMC exposes to users and other agents. It must not rely on private/internal APIs for test actions (only for introspection and telemetry).

### 2.2 High-Level Interactions

1. **Developer / CI** invokes:
   - `llmc usertest run tests/usertests/model_search.yaml`  
   or
   - `llmc usertest run --suite smoke`

2. **Scenario Orchestrator**:
   - Loads scenario definitions from YAML/JSON.
   - Spawns a **User Executor Agent** with a task and allowed interfaces.
   - Attaches a **Trace Recorder** to capture all tool calls and outputs.

3. **User Executor Agent**:
   - Behaves like a "slightly messy but goal-directed human user".
   - Uses only allowed interfaces and tools to achieve the scenario goal.

4. **Judge Agent**:
   - Reads scenario, trace, and derived metrics.
   - Evaluates against:
     - Hard rules (must-use / must-not-use tools).
     - Property checks (for example, metamorphic relations for search).
     - Heuristic/LLM-based scoring ("did the user accomplish the task?").
   - Emits a **RUTA Report** with incidents.

5. **Output**:
   - Human-readable markdown incident report.
   - Machine-readable JSON summary (for CI and future dashboards).

---

## 3. Architecture

### 3.1 Component Overview

1. **Scenario Registry**
   - Stores test scenarios in versioned files (for example, `tests/usertests/*.yaml`).
   - Provides APIs to list, load, and validate scenarios.

2. **User Test Runner (Orchestrator)**
   - CLI entrypoint and internal orchestrator.
   - Responsibilities:
     - Parse CLI args (scenario IDs, suites, filters).
     - Load scenarios from the registry.
     - For each scenario:
       - Create a **Run Context** (run ID, timestamps, environment tags).
       - Invoke the **User Executor Agent**.
       - Collect traces via the Trace Recorder.
       - Invoke the **Judge Agent**.
       - Persist results and emit summaries.

3. **User Executor Agent**
   - LLM (or LLM + tools) acting as the "user".
   - Receives:
     - System prompt: "You are RUTA-User, a simulated user..." (see section 5.1).
     - Scenario details: goal, constraints, allowed interfaces.
   - Executes via **LLMC normal interfaces/tools**:
     - CLI commands through TE (for example, `run_cmd` tools).
     - MCP tool calls.
     - HTTP endpoints (if applicable).
   - Emits structured "steps" (what it tried and why).

4. **Trace Recorder**
   - Cross-cutting component capturing:
     - Tool calls (name, arguments, result, success/fail, latency).
     - Prompts and responses (sanitized, possibly truncated).
     - Environment metadata (LLMC version, config, feature flags).
   - Writes to **JSONL** and/or a lightweight database for later querying.

5. **Judge Agent**
   - LLM plus rule engine that evaluates runs:
     - Parses scenario expectations and metamorphic relations.
     - Inspects traces and metrics.
     - Produces a **RUTA Report** with:
       - Overall verdict (PASS or FAIL).
       - Incident list (P0-P3).
       - Human-readable explanation.

6. **Property / Metamorphic Relation Engine (PMRE)**
   - Library for defining and running **property-based checks** and **metamorphic tests**, especially for search:
     - Relations like "adding a generic term must not reduce results to zero", "swapping word order should give similar results", and so on.
   - Pluggable: scenario files can reference built-in relations or define custom ones.

7. **Storage and Reporting**
   - File-based and/or SQLite for:
     - Run metadata (scenario, run ID, timestamp, verdict).
     - Traces (or pointers to trace files).
     - Reports (markdown and JSON).
   - CLI commands for quick inspection (for example, "list last 10 incidents").

### 3.2 Data Flow

1. **Test Invocation**
   - Developer runs `llmc usertest run --suite search-core`.

2. **Scenario Load**
   - Orchestrator loads matching scenarios from `tests/usertests/search/*.yaml`.

3. **Run Context Creation**
   - Orchestrator creates a run record with a unique `run_id`.

4. **Execution**
   - User Executor Agent is given the scenario; all actions flow through LLMC tools.
   - Trace Recorder logs every tool call and response.

5. **Evaluation**
   - Judge Agent plus PMRE evaluate the run, referencing traces and scenario expectations.

6. **Output**
   - RUTA Report written to `artifacts/ruta/<run_id>.md` and `artifacts/ruta/<run_id>.json`.

7. **CI / Developer Review**
   - CI reads JSON summaries to enforce gates.
   - Developers open markdown reports for detailed analysis.

---

## 4. Data Model and Contracts

### 4.1 Scenario Definition Schema (YAML)

Example (simplified):

```yaml
id: search_model_selection
version: 1
suite: search-core
description: >
  Ensure that queries involving the word "model" do not cause catastrophic result loss.
goal: |
  As a user, I want to search the LLMC RAG index for documentation related to model selection,
  routing strategies, and tiering.

interfaces:
  - mcp_search
  - cli_search

preconditions:
  - rag_index_built: true
  - min_docs: 5000

queries:
  base: "routing"
  variants:
    - "strategy"
    - "tier"
    - "model"
    - "routing model"
    - "routing strategy tier model"
    - "model selection"
    - "selection model"

expectations:
  must_use_tools:
    - rag_search
  must_not_use_tools: []
  properties:
    - name: no_catastrophic_result_drop_on_model
      type: metamorphic
      relation: result_count("routing") >> result_count("routing model")
      constraint: >
        result_count("routing") >= 1000 AND
        result_count("routing model") > 0
    - name: symmetric_word_order
      type: metamorphic
      relation: jaccard(results("model selection"), results("selection model"))
      constraint: jaccard >= 0.5

severity_policy:
  property_failures:
    no_catastrophic_result_drop_on_model: P0
    symmetric_word_order: P2
```

### 4.2 Trace Schema (JSONL)

Each line is a record:

```json
{
  "run_id": "ruta_2025-12-03T15:30:00Z_001",
  "timestamp": "2025-12-03T15:30:01.234Z",
  "step": 1,
  "agent": "user_executor",
  "event": "tool_call",
  "tool_name": "rag_search",
  "args": {"query": "routing model"},
  "result_summary": {"hits": 0, "error": null},
  "latency_ms": 42,
  "success": true
}
```

### 4.3 Report Schema (JSON)

```json
{
  "run_id": "ruta_2025-12-03T15:30:00Z_001",
  "scenario_id": "search_model_selection",
  "status": "FAIL",
  "incidents": [
    {
      "id": "INC-0001",
      "severity": "P0",
      "type": "PROPERTY_VIOLATION",
      "property": "no_catastrophic_result_drop_on_model",
      "summary": "Query 'routing model' returned 0 results, while 'routing' returned 6039.",
      "details": {
        "routing_results": 6039,
        "routing_model_results": 0
      }
    }
  ],
  "metrics": {
    "total_steps": 8,
    "total_tool_calls": 12,
    "duration_ms": 1832
  }
}
```

---

## 5. Agent Prompts and Behavior

### 5.1 User Executor Agent Prompt (Skeleton)

```
Role: You are RUTA-User, a simulated end user of LLMC.
Your job is to complete the given goal using only the public interfaces and tools you are allowed to use for this scenario.

Constraints:
- You may only use the interfaces listed (CLI, MCP, HTTP, and so on) as provided to you by tools.
- Use LLMC tools as a human user would (for example, search, enrichment triggers, shell commands in the sandbox).
- Do not access private or test-only APIs unless explicitly allowed.
- Prefer simple, robust actions over clever tricks.

Process:
1. Restate the goal in your own words.
2. Plan a short sequence of actions (1-5 steps).
3. Execute actions using the available tools.
4. After each action, briefly explain what you were trying to learn or achieve.
5. Stop when you believe the user goal is clearly achieved or clearly blocked.

Output Requirements:
- For each step, output:
  - What you did.
  - Which tools or interfaces you used.
  - Whether it helped.
- At the end, output a short summary:
  - Did you achieve the goal? Why or why not?
  - Any obvious bugs, missing capabilities, or confusing behavior?
```

The actual prompt will be extended with scenario-specific details at runtime (goal, constraints, tools, and so on).

### 5.2 Judge Agent Prompt (Skeleton)

```
Role: You are RUTA-Judge, an evaluator for LLMC user tests.
You receive:
- The scenario definition.
- A trace of the User Executor actions and tool calls.
- Derived metrics (result counts, latencies, errors).

Your tasks:
1. Determine whether the user goal was achieved.
2. Check that required tools were used appropriately and forbidden tools were not used.
3. Evaluate all scenario properties (including metamorphic relations, if any).
4. For each violation, generate a concise Incident with:
   - Severity (P0-P3).
   - Type (for example, TOOL_NOT_USED, CAPABILITY_LIE, PROPERTY_VIOLATION, UX_FAILURE).
   - Short summary and key evidence from the trace.
5. Produce an overall verdict: PASS or FAIL.

Output Format:
- A machine-readable JSON object matching the RUTA Report schema.
- A human-readable markdown section summarizing incidents and recommendations.
```

---

## 6. Phased Implementation Plan (with Difficulty Ratings)

Difficulty is 1-10, where:
- **1-3**: quick and straightforward (hours to a day).
- **4-6**: moderate (multi-day, some design work).
- **7-10**: complex (cross-cutting, higher risk, or multi-week).

### Phase 0 - Minimal Trace and Artifact Plumbing
**Difficulty: 3 / 10**

**Objectives:**
- Add a Trace Recorder that can be attached to LLMC tool calls and agent runs.
- Define and document:
  - Trace schema (JSONL).
  - Artifact directory layout (for example, `artifacts/ruta/`).
- Provide simple APIs:
  - `start_trace(run_id)` and `stop_trace(run_id)`.

**Deliverables:**
- Trace recorder module.
- Configurable artifact path in `llmc.toml`.
- Basic unit tests for trace writing and rotation.

### Phase 1 - Scenario Schema and Manual Runner
**Difficulty: 4 / 10**

**Objectives:**
- Define and validate Scenario YAML schema (see section 4.1).
- Implement a manual runner that:
  - Loads a scenario.
  - Executes a minimal "script" (without the User Executor Agent yet):
    - For search scenarios, runs queries directly via LLMC tools.
  - Writes a trace and a simple JSON summary.

**Deliverables:**
- `tests/usertests/` directory with 2-3 seed scenarios:
  - `search_model_selection` (the "model" bug family).
  - One enrichment scenario.
- CLI: `llmc usertest run <scenario_id> --manual`.
- Scenario validation tests.

### Phase 2 - User Executor Agent (Single-Agent Path)
**Difficulty: 6 / 10**

**Objectives:**
- Implement User Executor Agent with the prompt from section 5.1.
- Expose tools to the agent mirroring end-user capabilities:
  - CLI-style commands via TE (for example, `tool_run_cmd`, `tool_search`).
  - MCP tools for search and enrichment.
- Integrate with Trace Recorder so every tool call is logged.

**Key Design Points:**
- Ensure the agent cannot access internal/testing APIs unless the scenario allows it.
- Provide a deterministic-ish mode for CI (temperature caps, maybe fixed model).

**Deliverables:**
- Agent implementation and system prompt.
- CLI: `llmc usertest run <scenario_id>` (default uses User Executor).
- Tests for simple flows (for example, search, enrichment) passing through.

### Phase 3 - Judge Agent and Basic Property Checks
**Difficulty: 7 / 10**

**Objectives:**
- Implement Judge Agent using the prompt in section 5.2.
- Implement a basic property engine for simple checks:
  - Required tools used / forbidden tools avoided.
  - Simple metrics (`result_count > 0`, latency thresholds).
- Produce formal RUTA Reports (JSON and markdown).

**Key Challenges:**
- Designing a robust mapping between scenario expectations and trace data.
- Avoiding flaky judgments (define thresholds and tie-break rules).

**Deliverables:**
- Judge agent implementation.
- Property evaluation engine (non-metamorphic to start).
- Updated CLI: `llmc usertest run <scenario_id> --report` to generate full reports.
- Tests with known pass/fail scenarios.

### Phase 4 - Metamorphic Testing for Search and Core Workflows
**Difficulty: 7 / 10**

**Objectives:**
- Implement the Property / Metamorphic Relation Engine (PMRE) for search:
  - Relations like:
    - Result count monotonicity / non-catastrophic drops.
    - Word order symmetry (Jaccard overlap).
    - Stopword invariance.
- Integrate PMRE into Judge Agent.

**Deliverables:**
- PMRE library with configurable relations.
- Extended scenarios for search (3-5 metamorphic scenarios).
- Tests demonstrating detection of synthetic "model"-style bugs.

### Phase 5 - CI Integration and Regression Gates
**Difficulty: 5 / 10**

**Objectives:**
- Integrate RUTA with existing CI pipelines:
  - `llmc usertest run --suite smoke --format json --output ruta_ci.json`
- Define gating policies:
  - Fail CI if:
    - Any P0 incident detected.
    - P1 incidents above a configurable threshold.
- Provide summary CLI commands:
  - `llmc usertest list-runs` - last N runs, verdicts.
  - `llmc usertest show <run_id>` - open report.

**Deliverables:**
- CI-friendly commands and docs.
- Example CI config snippets.
- Tests checking correct exit codes based on incidents.

### Phase 6 - Advanced Scenario Generation and User Simulation Variants
**Difficulty: 8 / 10**

**Objectives:**
- Add Scenario Generator Agent to create variations of existing scenarios:
  - Vary user phrasing, partial information, mistakes.
  - Vary query formulations (synonyms, misspellings, and so on).
- Explore multi-persona simulations, inspired by research on user simulation and agent-based behavior modeling.
- Support "stress modes":
  - High-volume randomized runs within defined bounds.

**Deliverables:**
- Scenario generation tools (offline, checked into the repo).
- Additional suites like `stress-search` and `messy-users`.
- Safety guardrails to keep costs under control.

---

## 7. Risks and Mitigations

### 7.1 Flaky / Non-Deterministic Results
**Risk:** As with all LLM-based tests, the User Executor and Judge may occasionally produce inconsistent results.

**Mitigations:**
- Use deterministic config in CI (lower temperature, fixed models).
- Aggregate results over multiple runs for flaky scenarios.
- Prefer rule-based checks where possible (for example, property checks on numeric metrics).

### 7.2 Test Cost and Runtime
**Risk:** Complex simulations and large scenario suites can become expensive or slow.

**Mitigations:**
- Tag scenarios with cost categories (for example, `smoke`, `daily`, `weekly-heavy`).
- Allow CI config to select suites by tag.
- Cache and reuse some traces where appropriate.

### 7.3 Overfitting to Current Behavior
**Risk:** Properties and scenarios may encode assumptions that become invalid as LLMC evolves.

**Mitigations:**
- Keep scenarios under version control with clear intent docs.
- Regularly review and prune stale or over-constraining properties.
- Use high-level properties where possible (for example, "no catastrophic drops") instead of brittle exact numbers.

### 7.4 Security and Sandbox Leakage
**Risk:** User Executor Agent might accidentally discover paths that bypass sandbox assumptions.

**Mitigations:**
- Ensure sandbox boundaries are actually enforced at the platform level.
- Treat RUTA findings as input to the Security Testing Agent roadmap.
- Add specific scenarios to probe sandbox boundaries, informed by security practices.

---

## 8. Conclusion

RUTA formalizes something you are already doing "by vibe": watching an agent flail around, noticing when it writes a janky sed-clone script because the environment lied to it, or when a single token like "model" silently zeroes out search.

By building the Ruthless User Testing Agent as a structured, multi-phase system, LLMC gains:

- **Continuous, automated detection** of user-facing regressions.
- **Clear, actionable incident reports** instead of vague "it feels off" impressions.
- A foundation for future agent testing, evaluation, and observability work that fits your local-first, TE-driven, sharp-edges philosophy.

**Start with Phase 0-2** to get traces, scenarios, and a basic simulated user in place. Then layer on the Judge plus metamorphic testing to catch deep weirdness like the "model" bug before it gets anywhere near production.
