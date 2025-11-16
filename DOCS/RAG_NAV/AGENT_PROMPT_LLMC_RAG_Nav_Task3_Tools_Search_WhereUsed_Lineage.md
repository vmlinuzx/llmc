# Agent Prompt — Apply LLMC RAG Nav Task 3 Patch (RAG-only Tools)

You are an implementation agent working on the LLMC repository.

## Goal

Integrate the **Task 3 RAG Nav RAG-only tools** patch, which adds:

- Result dataclasses to `tools/rag_nav/models.py`.
- Search/where-used/lineage helpers in `tools/rag_nav/tool_handlers.py`.
- New CLI subcommands in `tools/rag_nav/cli.py`.
- Tests under `tests/test_rag_nav_tools.py`.
- Documentation under `DOCS/RAG_NAV/` for Task 3.

This patch assumes Tasks 1 and 2 are already present (models,
metadata, graph builder, and basic CLI).

## Instructions

1. Apply the contents of the provided patch zip into the LLMC repo root,
   preserving the directory structure:

   - `tools/rag_nav/__init__.py`
   - `tools/rag_nav/models.py`
   - `tools/rag_nav/tool_handlers.py`
   - `tools/rag_nav/cli.py`
   - `tests/test_rag_nav_tools.py`
   - `DOCS/RAG_NAV/SDD_RAG_Nav_Task3_Tools_Search_WhereUsed_Lineage.md`
   - `DOCS/RAG_NAV/Implementation_SDD_RAG_Nav_Task3_Tools_Search_WhereUsed_Lineage.md`
   - `DOCS/RAG_NAV/RAG_Nav_Task3_System_Overview.md`
   - `DOCS/RAG_NAV/AGENT_PROMPT_LLMC_RAG_Nav_Task3_Tools_Search_WhereUsed_Lineage.md`

2. Ensure `scripts/llmc-rag-nav` from Task 2 is still present and
   executable.

3. Run tests for the new tools:

   ```bash
   pytest tests/test_rag_nav_tools.py
   ```

4. From the repo root, exercise the CLI manually (after building
   the graph for the real repo):

   ```bash
   scripts/llmc-rag-nav build-graph --repo .
   scripts/llmc-rag-nav search --repo . --query some_symbol --limit 5
   scripts/llmc-rag-nav where-used --repo . --symbol some_symbol --limit 5
   scripts/llmc-rag-nav lineage --repo . --symbol some_symbol --direction downstream --max-results 5
   ```

5. Inspect the JSON output to confirm that:

   - Results include snippets and file paths.
   - `source` is `"RAG_GRAPH"`.
   - `freshness_state` is `"UNKNOWN"`.

6. Commit with a message similar to:

   ```text
   feat(rag_nav): add RAG-only search/where-used/lineage tools (Task 3)
   ```

7. Open a pull request referencing the Task 3 SDD and Implementation
   SDD, and note that this is still RAG-only; freshness/fallback
   routing will be added in Task 4.

