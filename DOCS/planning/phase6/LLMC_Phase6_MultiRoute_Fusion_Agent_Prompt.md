# LLMC – Phase 6 Multi-Route Retrieval & Score Fusion (Agent Implementation Prompt)

## Title

Implement optional multi-route retrieval and score fusion for docs + code (Phase 6)

---

## Context

LLMC already has deterministic routing for:

- **Ingest (slices)** – based on `slice_type`:
  - `slice_type="code"` → route `code` → `code_jina` + `emb_code`
  - Others → route `docs` → `default_docs` + `emb_docs`
- **Queries** – based on `classify_query()`:
  - `route_name="code"` → `code` route.
  - `route_name="docs"` → `docs` route.
- **Enrichment & prompts** – content-type metadata is present and used in prompts.

Currently, each query is sent to **exactly one route** (docs *or* code). In practice, many queries could benefit from **both**:

- “Explain how this function works” → code + nearby docs.
- “Where is X configured in the codebase” → code first, docs second.
- “How do I configure `<thing>` in LLMC?” → docs first, but there might be code examples.

You are implementing **Phase 6**, which introduces **optional multi-route retrieval** and simple score fusion for **docs + code**.

---

## Goal of this task (Phase 6)

Add an **optional multi-route retrieval mode** that:

- Given a query and its primary route (`code` or `docs`):
  - Optionally also queries one or more **secondary routes**.
  - Fuses the results with a simple weighted score combination.
- Is fully controlled via config and defaults to **disabled** (single-route behavior).
- Works only with the existing routes (`docs` and `code`) – no new routes yet.

The result: callers can enable a “docs+code” or “code+docs” combo per query type, while keeping routing deterministic and understandable.

---

## Requirements

### 1. Config surface for multi-route behavior

Extend `llmc.toml` to support multi-route retrieval configuration. A suggested structure:

```toml
[routing.options]
enable_query_routing = true
enable_multi_route   = false

# Define a primary route and one or more secondary routes to fan out to.
# Each secondary route has a weight (used in score fusion).
[routing.multi_route.code_primary]
primary   = "code"
secondary = [
  { route = "docs", weight = 0.5 }
]

[routing.multi_route.docs_primary]
primary   = "docs"
secondary = [
  { route = "code", weight = 0.3 }
]
```

Guidelines:

- `enable_multi_route` defaults to `false` if omitted.
- `routing.multi_route.*` sections are **optional**:
  - If there is no section for a given primary route, multi-route is disabled for that primary route even if `enable_multi_route` is `true`.
- We only care about `code_primary` and `docs_primary` in this phase.

You can adjust the exact TOML shape to fit existing config helpers (e.g., list-of-tables vs arrays), but it should be:

- Human-editable.
- Easy to reason about: “primary route + list of secondary routes & weights”.

### 2. Multi-route retrieval pipeline

Modify the retrieval code path that currently:

1. Calls `classify_query()` to get `route_name`.
2. Resolves this to a single `{profile, index}`.
3. Embeds the query with that profile and searches that index.

New behavior when `enable_multi_route=true`:

1. Call `classify_query()` → `primary_route_name` (`"docs"` or `"code"`).
2. Check if multi-route config exists for that primary route:
   - If no config, behave as Phase 3 (single route).
3. If config exists:
   - Build a list of `(route_name, weight)`:
     - Always include `(primary_route_name, 1.0)` as the primary route.
     - Add all configured secondary routes from `routing.multi_route.<primary>`.
   - For each route:
     - Resolve `{profile_name, index_name}` via `embeddings.routes.*`.
     - Embed the query using the profile (you may reuse the same query embedding if two routes share the same profile).
     - Run a top-k search per index (k can be configurable or a small fixed value like 20).
4. Score fusion:
   - Normalize scores per route:
     - Use a simple normalization (e.g., min-max normalization within each route’s results) to get scores in [0, 1].
   - Apply route weights:
     - `final_score = normalized_score * weight`.
   - Merge all result rows across routes:
     - Group by `slice_id` (or equivalent).
     - For a slice appearing in multiple routes, use the **max** of its fused scores (or sum; choose one and document it).
   - Sort by `final_score` descending and take top-N overall.
5. Return the fused result set to the caller.

When `enable_multi_route=false`:

- Keep existing Phase 3 behavior (single-route retrieval).

### 3. Backwards compatibility & safety

- If `enable_multi_route=true` but:
  - The multi-route config for that primary route is missing, OR
  - Any secondary route cannot be resolved to a valid `{profile, index}`:

  Then:

  - Log a warning.
  - Fall back to primary route only (single-route behavior).

- Do not let a typo in multi-route config break the entire system.

### 4. Logging / metrics for multi-route

Extend routing metrics from Phase 5 to also track:

- When multi-route retrieval is used:
  - Number of queries that triggered multi-route.
  - Per-primary-route stats (e.g., `code_primary`, `docs_primary`).
- Per-route contributions:
  - Optionally, counts of how often a route’s results actually made it into the final top-N list.

Logging:

- For debug-level logs, log a compact summary per multi-route query:
  - primary route
  - secondary routes used
  - k per route
  - how many final results came from each route.

Do not log full query text, just enough metadata to understand behavior.

---

## 5. Tests

Add tests in line with the project’s testing style.

### 5.1 Unit tests for fusion

Create a small pure function for score fusion, for example:

```python
def fuse_scores(route_results, route_weights):
    """route_results: dict route_name -> list of (slice_id, raw_score)
       route_weights: dict route_name -> weight (float)
       Returns: list of (slice_id, fused_score) sorted desc.
    """
```

Test cases:

- Single route only:
  - Should behave like normalized scores of that route.
- Two routes with different raw score ranges:
  - Ensure normalization is per-route (e.g., high scores from code don’t dominate docs only because of scale).
- Duplicate slice_ids across routes:
  - Ensure fused score picks max or sum (depending on chosen rule), and no duplicates in final results.

### 5.2 Integration tests

Include tests that use mocked embedding+index layers:

- `enable_multi_route=false`:
  - Behavior matches Phase 3 (single route, no changes).
- `enable_multi_route=true`, `code_primary` configured:
  - A code-like query:
    - Triggers multi-route.
    - Produces results from both `emb_code` and `emb_docs`.
- `enable_multi_route=true`, but secondary route misconfigured:
  - Logs a warning.
  - Falls back to single-route behavior.

---

## Style & Constraints

- Keep the implementation **simple and deterministic**:
  - No learned weighting or ML-based rerankers in this phase.
- Reuse existing config, routing, and metrics abstractions.
- Centralize multi-route logic so it can be disabled/tuned easily (e.g., a dedicated module or functions).

---

## Deliverables

1. Updated config parsing:
   - `routing.options.enable_multi_route`
   - `routing.multi_route.*` structures.
2. Retrieval pipeline changes:
   - Multi-route fan-out and score fusion when enabled.
   - Safe fallbacks when misconfigured.
3. Metrics & logging:
   - New counters and debug logs for multi-route usage.
4. Tests:
   - Fusion logic unit tests.
   - Integration tests for multi-route vs single-route behavior.
5. Brief docs update:
   - Add a section in `ROUTING.md` explaining:
     - How to enable multi-route retrieval.
     - Example configs for:
       - “code primary, docs secondary”
       - “docs primary, code secondary”
     - How score fusion works at a high level.