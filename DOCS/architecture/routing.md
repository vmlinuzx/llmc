# RAG Routing System

This document explains the routing system used within LLMC's Retrieval Augmented Generation (RAG) components. This system determines how different types of content (slices) are embedded and indexed, and how queries are routed to the appropriate indices for retrieval.

---

## 1. Overview

LLMC employs a deterministic, content-type-aware routing layer for embeddings and enrichment. This system ensures that:
- **Ingested content** (`slices`) is directed to specific embedding profiles and indices based on its detected type (e.g., code, documentation).
- **Queries** are classified and routed to the most relevant content index, optimizing retrieval.
- **Enrichment records** are tagged with consistent content-type metadata.

The routing logic is driven by configuration in `llmc.toml` and aims for robustness, configurability, and observability.

---

## 2. Data Flow

### 2.1. Slice Classification (Ingest)

When a new slice of content is ingested, it undergoes classification to determine its `slice_type` (e.g., `code`, `docs`, `config`, `data`, `other`). This classification is performed by the `llmc.routing.content_type.classify_slice` function, leveraging heuristics such as:
- **File extension**: (e.g., `.py` for `code`, `.md` for `docs`).
- **Shebang detection**: (e.g., `#!/bin/bash` in a script).
- **Syntax/heuristic scan**: Detecting code-like tokens (`class`, `def`, `{`, `}`) versus prose.

The determined `slice_type`, along with `slice_language` (e.g., `python`, `javascript`), `confidence`, and `reasons`, is persisted as metadata on the slice record in the database.

### 2.2. Slice to Route Mapping

Once a `slice_type` is determined, it is mapped to a `route_name` (e.g., `"code"`, `"docs"`) via the `routing.slice_type_to_route` section in `llmc.toml`. This mapping is handled by the `llmc.rag.config.get_route_for_slice_type` helper function.

### 2.3. Route to Embedding Profile & Index Mapping

Each `route_name` then maps to a specific `embedding_profile` and `embedding_index`. This mapping is defined in the `embeddings.routes.*` section of `llmc.toml` and resolved by the `llmc.rag.config.resolve_route` helper function.

- An `embedding_profile` (defined under `embeddings.profiles.*`) specifies the embedding model, its dimension (`dim`), provider, and other characteristics.
- An `embedding_index` refers to the specific database table (e.g., `emb_docs`, `emb_code`) where the generated embeddings for that content type will be stored.

The slice content is then embedded using the designated profile and stored in the corresponding index.

### 2.4. Query Routing

When a query is submitted, it undergoes classification by `llmc.routing.query_type.classify_query` to determine if it is "code-like" or "docs-like." This classification considers:
- **Tool context**: If an active tool is code-oriented (e.g., `code_refactor`), the query is likely `code`.
- **Query content heuristics**: Presence of programming keywords, symbols, or code snippets.

Based on this classification, and if `routing.options.enable_query_routing` is enabled, the query is routed to the appropriate embedding index (`emb_code` or `emb_docs`) for retrieval. The query itself is embedded using the model associated with the chosen route's profile.

---

## 3. Configuration Knobs

All routing decisions are data-driven and configurable in `llmc.toml`.

### `[embeddings.profiles.<profile_name>]`

Defines the characteristics of an embedding model.

- **`provider`**: (e.g., `openai`, `ollama`, `sentence-transformer`, `hash`).
- **`model`**: The specific model identifier (e.g., `text-embedding-3-large`, `jina-embeddings-v2-base-code:q5_k_m`).
- **`dim`**: The dimension of the embedding vectors.
- **`cost_class`**: (e.g., `low`, `medium`, `high`) for cost tracking.
- **`capabilities`**: (e.g., `natural_language`, `code`) indicating what the model is good at.

Example:
```toml
[embeddings.profiles.default_docs]
provider = "openai"
model = "text-embedding-3-large"
dim = 3072
cost_class = "medium"
capabilities = ["natural_language"]

[embeddings.profiles.code_jina]
provider = "ollama"
model = "jina-embeddings-v2-base-code:q5_k_m"
dim = 768
cost_class = "low"
capabilities = ["code"]
```

### `[embeddings.routes.<route_name>]`

Maps a logical `route_name` to an `embedding_profile` and an `embedding_index`.

- **`profile`**: References a `<profile_name>` defined in `embeddings.profiles.*`.
- **`index`**: The name of the database table used for storing embeddings for this route (e.g., `emb_docs`, `emb_code`).

Example:
```toml
[embeddings.routes.docs]
profile = "default_docs"
index   = "emb_docs"

[embeddings.routes.code]
profile = "code_jina"
index   = "emb_code"
```

### `[routing.slice_type_to_route]`

Defines how a detected `slice_type` maps to a `route_name`.

Example:
```toml
[routing.slice_type_to_route]
code        = "code"
docs        = "docs"
erp_product = "docs"   # Example: ERP content routes to docs currently
config      = "docs"
data        = "docs"
other       = "docs"
```

### `[routing.options]`

Contains flags controlling routing behavior.

- **`enable_query_routing`**: A boolean flag (defaults to `false` if omitted) that enables or disables query routing. If `false`, all queries default to the "docs" route.

Example:
```toml
[routing.options]
enable_query_routing = true
```

---

## 4. Fallbacks & Edge Cases

The routing system is designed to be robust against misconfiguration or missing data:

-   **Missing `routing.slice_type_to_route` entry**: If a `slice_type` is not explicitly mapped, it will default to the `"docs"` route. A warning will be logged (once per unique missing type) to alert the user.
-   **Missing `embeddings.routes.<route_name>` entry**: If a specified `route_name` (e.g., `"code"`) does not have a corresponding entry in `embeddings.routes.*`, the system will fall back to the `"docs"` route. A warning will be logged with context.
    -   **Critical**: If the `"docs"` route itself is missing, this is considered a critical configuration error, and the system will raise a `ConfigError` and fail early.
-   **Incomplete `embeddings.routes.<route_name>` definition**: If a route entry is missing either `profile` or `index` fields, it will fall back to the `"docs"` route (similar to a missing route entry). A warning will be logged.
    -   **Critical**: If the `"docs"` route is incompletely defined, a `ConfigError` will be raised.
-   **Missing `embeddings.profiles.<profile_name>` entry**: If a route references a `profile_name` that does not exist under `embeddings.profiles.*`:
    -   If the target route is `"docs"`, it will attempt to fall back to a `default_docs` profile. A warning will be logged. If `default_docs` is also missing, a `ConfigError` will be raised.
    -   For any other route type (non-`"docs"`), this is considered a critical configuration error, and a `ConfigError` will be raised.
-   **`routing.options.enable_query_routing` omitted**: This flag defaults to `false` for backwards compatibility.
-   **Unsafe Query Routing**: If `enable_query_routing` is `true`, but the classified query route (e.g., `"code"`) cannot be safely resolved (e.g., due to a missing profile or index for that route), the system will log a warning and fall back to the `"docs"` route for that query.
-   **Invalid Query Index**: If searching against a resolved query index fails (e.g., the table doesn't exist or is corrupt), the system will attempt to fall back to the generic `embeddings` table and log a warning.

---

## 5. Examples

### 5.1. Minimal Docs-Only Configuration

To use only the default documentation embedding and index:

```toml
[embeddings.profiles.default_docs]
provider = "openai"
model = "text-embedding-3-large"
dim = 3072

[embeddings.routes.docs]
profile = "default_docs"
index   = "emb_docs"

[routing.slice_type_to_route]
code        = "docs"
docs        = "docs"
erp_product = "docs"
config      = "docs"
data        = "docs"
other       = "docs"

[routing.options]
enable_query_routing = false # Default if omitted, explicit here
```

### 5.2. Docs + Jina Code Routing

To enable separate routing for code using a local Jina model via Ollama:

```toml
[embeddings.profiles.default_docs]
provider = "openai"
model = "text-embedding-3-large"
dim = 3072

[embeddings.profiles.code_jina]
provider = "ollama"
model = "jina-embeddings-v2-base-code:q5_k_m"
dim = 768

[embeddings.routes.docs]
profile = "default_docs"
index   = "emb_docs"

[embeddings.routes.code]
profile = "code_jina"
index   = "emb_code"

[routing.slice_type_to_route]
code        = "code"
docs        = "docs"
erp_product = "docs"
config      = "docs"
data        = "docs"
other       = "docs"

[routing.options]
enable_query_routing = true
```

### 5.3. Adding a New Slice Type

To add a new `slice_type="sql"` that should also be routed to the `code` embedding profile:

1.  Ensure your `classify_slice` logic (or an external classifier) is updated to identify `slice_type="sql"`.
2.  Update `llmc.toml` (no new profiles or routes needed if routing to `code`):

    ```toml
    [routing.slice_type_to_route]
    # ... existing mappings ...
    sql = "code" # Route SQL files to the existing code embedding route
    ```

---

## 6. Multi-Route Retrieval (Fan-out & Fusion)

Phase 6 introduces optional **multi-route retrieval**, where a single query can be sent to multiple routes (indices) in parallel, and the results are fused into a single ranked list. This is useful when a query might benefit from both code and documentation results (e.g., "How is X implemented and documented?").

### 6.1. Configuration

To enable this, use the `[routing.multi_route.<primary_route_name>_primary]` configuration block.

- **`enable_multi_route`**: Must be set to `true` in `[routing.options]`.
- **`[routing.multi_route.<primary>_primary]`**: Defines the secondary routes for a given primary route.
    - `primary`: The name of the primary route (must match the section key).
    - `secondary`: A list of tables defining `route` and `weight`.

Example:
```toml
[routing.options]
enable_query_routing = true
enable_multi_route = true

# If primary route is 'code', also query 'docs' with 0.5 weight
[routing.multi_route.code_primary]
primary = "code"
secondary = [
  { route = "docs", weight = 0.5 }
]

# If primary route is 'docs', also query 'code' with 0.3 weight
[routing.multi_route.docs_primary]
primary = "docs"
secondary = [
  { route = "code", weight = 0.3 }
]
```

### 6.2. Fusion Logic

When multiple routes return results:
1.  **Normalization**: Scores from each route are normalized to the [0, 1] range (min-max normalization) to account for different embedding model scales.
2.  **Weighting**: Normalized scores are multiplied by the configured `weight`. (Primary route always has weight 1.0).
3.  **Fusion**: Results are merged by `slice_id`. If a slice appears in multiple routes, the **maximum** weighted score is kept.
4.  **Ranking**: The final list is sorted by the fused score.

### 6.3. Safety

- If `enable_multi_route` is `false` (default), standard single-route retrieval is used.
---

## 7. ERP/Product Route

Phase 7 introduces a dedicated **ERP route** for product-related content. This separates ERP/PIM data (SKUs, specs, catalog info) from general documentation and code, allowing for targeted retrieval and potential future specialization (e.g. different chunking or models).

### 7.1. Logic

- **Ingest**: Slices originating from ERP imports or containing structured product data (JSON/CSV with SKUs) are classified as `slice_type="erp_product"` and routed to the `erp` route.
- **Query**: Queries containing SKUs (e.g., `W-44910`) or product keywords (`SKU`, `UPC`, `model number`) are classified as `route_name="erp"`.
- **Retrieval**: The `erp` route uses its own index (`emb_erp`) but currently reuses the documentation embedding model.

### 7.2. Configuration

To enable the ERP route:

1. Define the route in `llmc.toml`:
   ```toml
   [embeddings.routes.erp]
   profile = "docs"     # Reuse existing docs profile or define a custom one
   index   = "emb_erp"  # Separate index table
   ```

2. Map the slice type:
   ```toml
   [routing.slice_type_to_route]
   erp_product = "erp"
   ```

3. (Optional) Add multi-route fan-out:
   ```toml
   [routing.multi_route.erp_primary]
   primary = "erp"
   secondary = [
     { route = "docs", weight = 0.2 }
   ]
   ```


