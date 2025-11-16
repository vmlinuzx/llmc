# Agent Prompt — Apply LLMC RAG Nav Task 4 Patch (Context Gateway & Routing)

You are an implementation agent working on the LLMC repository.

## Goal

Integrate the **Task 4 RAG Nav Context Gateway & Routing** patch,
which adds:

- `tools/rag_nav/gateway.py` with `compute_route`.
- Updated `tools/rag_nav/models.py` with `FreshnessState` and
  `SourceTag`.
- Updated `tools/rag_nav/tool_handlers.py` that routes between
  RAG graph and local fallback based on `compute_route`.
- Updated `tools/rag_nav/cli.py` (no behavioural change except
  underlying routing).
- New tests in `tests/test_rag_nav_gateway.py`.
- Updated `tests/test_rag_nav_tools.py` to reflect routing.
- Documentation under `DOCS/RAG_NAV/` for Task 4.

This patch assumes Tasks 1–3 are already integrated.

## Instructions

1. Apply the contents of the provided patch zip into the LLMC repo root,
   preserving the directory structure:

   - `tools/rag_nav/__init__.py`
   - `tools/rag_nav/models.py`
   - `tools/rag_nav/gateway.py`
   - `tools/rag_nav/tool_handlers.py`
   - `tools/rag_nav/cli.py`
   - `tests/test_rag_nav_gateway.py`
   - `tests/test_rag_nav_tools.py`
   - `DOCS/RAG_NAV/SDD_RAG_Nav_Task4_Context_Gateway_Routing.md`
   - `DOCS/RAG_NAV/Implementation_SDD_RAG_Nav_Task4_Context_Gateway_Routing.md`
   - `DOCS/RAG_NAV/RAG_Nav_Task4_System_Overview.md`
   - `DOCS/RAG_NAV/AGENT_PROMPT_LLMC_RAG_Nav_Task4_Context_Gateway_Routing.md`

2. Ensure previous tasks are present:
   - `tools.rag_nav.metadata`
   - `tools.rag_nav.tool_handlers.build_graph_for_repo`
   - `scripts/llmc-rag-nav` wrapper.

3. Run tests:

   ```bash
   pytest tests/test_rag_nav_gateway.py tests/test_rag_nav_tools.py
   ```

4. From the repo root, exercise the CLI manually:

   ```bash
   scripts/llmc-rag-nav build-graph --repo .
   scripts/llmc-rag-nav search --repo . --query some_symbol --limit 5
   scripts/llmc-rag-nav where-used --repo . --symbol some_symbol --limit 5
   scripts/llmc-rag-nav lineage --repo . --symbol some_symbol --direction downstream --max-results 5
   ```

   Observe the JSON outputs, including:

   - `source`: `"RAG_GRAPH"` or `"LOCAL_FALLBACK"`
   - `freshness_state`: `"FRESH"`, `"STALE"`, or `"UNKNOWN"`

5. Commit with a message similar to:

   ```text
   feat(rag_nav): add context gateway and freshness routing (Task 4)
   ```

6. Open a pull request referencing the Task 4 SDD and Implementation
   SDD, and note that this completes the initial RAG Nav MVP. Future
   work can focus on richer graph semantics and MCP integration.

