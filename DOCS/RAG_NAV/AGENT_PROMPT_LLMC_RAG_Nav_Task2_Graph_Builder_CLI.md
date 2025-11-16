# Agent Prompt — Apply LLMC RAG Nav Task 2 Patch (Graph Builder & CLI)

You are an implementation agent working on the LLMC repository.

## Goal

Integrate the **Task 2 RAG Nav Graph Builder & CLI** patch, which adds:

- `tools/rag_nav/tool_handlers.py` with `build_graph_for_repo`.
- `tools/rag_nav/cli.py` with `build-graph` and `status` subcommands.
- `tests/test_rag_nav_build_graph.py`.
- A tiny fixture under `tests/fixtures/rag_nav_demo/` (for future use).
- `scripts/llmc-rag-nav` convenience wrapper.
- Documentation under `DOCS/RAG_NAV/` for Task 2.

This patch assumes Task 1 (`tools.rag_nav.models` and
`tools.rag_nav.metadata`) is already present.

## Instructions

1. Apply the contents of the provided patch zip into the LLMC repo root,
   preserving the directory structure:

   - `tools/rag_nav/__init__.py`
   - `tools/rag_nav/tool_handlers.py`
   - `tools/rag_nav/cli.py`
   - `tests/test_rag_nav_build_graph.py`
   - `tests/fixtures/rag_nav_demo/demo_module.py`
   - `scripts/llmc-rag-nav`
   - `DOCS/RAG_NAV/SDD_RAG_Nav_Task2_Graph_Builder_CLI.md`
   - `DOCS/RAG_NAV/Implementation_SDD_RAG_Nav_Task2_Graph_Builder_CLI.md`
   - `DOCS/RAG_NAV/RAG_Nav_Task2_System_Overview.md`
   - `DOCS/RAG_NAV/AGENT_PROMPT_LLMC_RAG_Nav_Task2_Graph_Builder_CLI.md`

2. Ensure the script `scripts/llmc-rag-nav` is executable if your
   environment requires it:

   ```bash
   chmod +x scripts/llmc-rag-nav
   ```

3. Run the new tests:

   ```bash
   pytest tests/test_rag_nav_build_graph.py
   ```

4. From the repo root, exercise the CLI manually:

   ```bash
   scripts/llmc-rag-nav build-graph --repo .
   scripts/llmc-rag-nav status --repo . --json
   ```

   Verify that:

   - `.llmc/rag_graph.json` is created.
   - `.llmc/rag_index_status.json` is updated and marked `fresh`.
   - The JSON output from `status` contains the expected fields.

5. Commit with a message similar to:

   ```text
   feat(rag_nav): add graph builder and CLI (Task 2)
   ```

6. Open a pull request referencing the Task 2 SDD and Implementation
   SDD, and note that this is the second incremental step toward the
   RAG Nav where-used/lineage feature.

