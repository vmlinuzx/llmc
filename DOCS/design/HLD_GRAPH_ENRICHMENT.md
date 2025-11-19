# HLD: Phase 2 - Graph Enrichment (Database to SchemaGraph Integration)

## 1. Goal
To seamlessly integrate enrichment data (facts extracted by LLMs and stored in the SQLite enrichment database) directly into the SchemaGraph. This aims to create a unified, "super-graph" where structural code relationships are enhanced with semantic meaning, thereby making RAG tools and lower-tier LLMs significantly "smarter" and more capable.

## 2. Problem Statement
Currently, the LLMC RAG system maintains two valuable but disconnected sources of truth about the codebase:
1.  The **SchemaGraph**: Represents the structural relationships (calls, definitions, imports) derived from AST analysis.
2.  The **Enrichment Database**: Stores LLM-generated semantic facts (summaries, usage, caveats) linked to specific code spans (file path + line ranges).

The absence of a direct, robust link between these two means that RAG tools operating on the SchemaGraph cannot leverage the rich semantic context from the Enrichment Database, leading to less informative responses and underutilized LLM analysis.

## 3. Proposed Solution: The Enriched SchemaGraph Builder
We will extend the graph building process to fetch relevant enrichment data from the SQLite database and attach it as metadata to corresponding entities (nodes) within the SchemaGraph. This creates an "Enriched SchemaGraph" which becomes the primary artifact for RAG operations.

## 4. Key Components
*   **Existing SchemaGraph Builder**: The current component responsible for generating the structural `rag_graph.json` from code analysis.
*   **Enrichment Database Helpers**: New or extended functions (`tools.rag.enrichment_db_helpers`) to efficiently query the SQLite database for enrichment records based on file path and span/entity identifiers.
*   **Graph Enrichment Logic**: The core logic responsible for iterating through SchemaGraph entities, querying the enrichment database, and merging relevant enrichment metadata into the graph entities. This will reside within or be orchestrated by `tools.rag_nav.tool_handlers.build_graph_for_repo`.
*   **Enriched SchemaGraph Schema**: Updates to the `tools.rag.schema.Entity` definition to include a flexible `metadata` field (e.g., a dictionary) to store the attached enrichment data.

## 5. Data Flow (High-Level)
1.  **Input**: The process starts with a `repo_root` and potentially configuration (e.g., path to enrichment DB).
2.  **Initial Graph Generation**: The existing SchemaGraph builder generates the base structural graph (`SchemaGraph`).
3.  **Enrichment Querying**: For each `Entity` (e.g., function, class) in the base `SchemaGraph`:
    *   Extract its unique identifier (e.g., `file_path`, `start_line`, `end_line` or `span_hash`).
    *   Query the Enrichment Database for matching enrichment records (`EnrichmentRecord`).
4.  **Metadata Merging**: Merge the retrieved enrichment data into a designated `metadata` field within the `Entity` object. This could involve structuring the enrichment as key-value pairs (e.g., `metadata: { "summary": "...", "usage_guide": "..." }`). Conflict resolution (e.g., multiple summaries for the same span) will be defined in the SDD.
5.  **Output**: The fully enriched `SchemaGraph` is serialized and saved as `repo_root/.llmc/rag_graph.json`, replacing the previous structural-only graph.

## 6. Key Decisions / Constraints
*   **In-Memory Processing**: The graph enrichment process will operate in-memory. The base graph is loaded, enriched, and then re-serialized. This avoids complex incremental updates on the graph file.
*   **Performance**: The enrichment query process must be efficient. Indexing on `file_path` and span coordinates in the SQLite DB is assumed.
*   **Backward Compatibility**: Existing graph consumers should ideally still function, ignoring new `metadata` fields if they don't understand them. The enriched graph will supersede the structural graph.
*   **No New Services**: This HLD does not introduce new long-running services or external dependencies. It extends an existing batch process.

## 7. Open Questions (for SDD)
*   **Schema for Enrichment Metadata**: What is the exact structure of the `metadata` dictionary within a `SchemaGraph.Entity`? (e.g., flat key-value, nested object, list of facts).
*   **Matching Strategy**: What is the definitive strategy for matching `SchemaGraph.Entity` to `EnrichmentRecord`? (e.g., exact `span_hash`, file path + line ranges with fuzzy matching). How to handle multiple matches?
*   **Conflict Resolution**: If multiple enrichment records apply to a single graph entity, how are they combined or prioritized? (e.g., most recent, specific types preferred).
*   **Error Handling**: What happens if the enrichment DB is unavailable or corrupted during graph building? (e.g., log, continue without enrichment, fail early).
*   **Test Data Generation**: How will we create realistic test data (both graph and enrichment DB) for integration tests?

## 8. Test Strategy
*   **Unit Tests**:
    *   Validate the `Enrichment Database Helpers` for correct querying and record retrieval.
    *   Test the `Graph Enrichment Logic` in isolation: provide mock graph entities and mock enrichment data, assert correct merging into entity metadata.
*   **Integration Tests**:
    *   **"Happy Path"**: Build a temporary repository with known code and associated enrichment data in its SQLite DB. Run the enriched graph builder, then load and assert that specific graph entities contain the expected enrichment metadata.
    *   **"No Enrichment"**: Build a graph for a repo without any enrichment data; assert that graph entities have empty or no enrichment metadata, and the builder completes successfully.
    *   **"Partial Enrichment"**: Build a graph where only some entities have enrichment data; assert that only the relevant entities are enriched.
    *   **"DB Unavailable/Corrupt"**: Simulate an unavailable or corrupt enrichment DB during graph building; assert graceful degradation (e.g., graph built without enrichment, appropriate logging).
    *   **Golden File Regression**: Use existing (or new) golden `rag_graph.json` files to ensure that the structural integrity of the graph is maintained after enrichment.

## 9. Impact / Risks
*   **Impact**: Significantly enhances the semantic understanding capabilities of RAG tools, enabling more intelligent code analysis, search, and generation. Directly supports the "making Minimax smart" objective.
*   **Risks**:
    *   **Performance Degradation**: Iterating through all graph entities and querying the DB could be slow for very large repositories. (Mitigation: Optimize DB queries, consider batching).
    *   **Data Consistency**: Mismatches or staleness between code, graph, and enrichment data could lead to incorrect or misleading information. (Mitigation: Freshness checks, clear matching strategy).
    *   **Schema Evolution**: Changes to the enrichment data schema could require corresponding changes in the graph enrichment logic. (Mitigation: Flexible `metadata` field, versioning).