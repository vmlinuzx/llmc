# LLMC Routing Evaluation & Abstraction

Phase 8 introduced a formal **Router Abstraction** and an **Evaluation Harness** to measure routing and retrieval quality.

---

## 1. Router Abstraction

The routing logic is now encapsulated behind a `Router` interface defined in `llmc/routing/router.py`.

```python
class Router(ABC):
    def decide_route(self, query_text: str, tool_context: Optional[Dict]) -> Dict[str, Any]:
        """
        Returns:
            {
                "route_name": str,       # "docs", "code", "erp"
                "confidence": float,
                "reasons": list[str]
            }
        """
```

### Modes

The router implementation is chosen via `llmc.toml`:

```toml
[routing.options]
router_mode = "deterministic" # Default
```

- **`deterministic`**: Wraps the existing rule-based classifiers (`classify_query`).
- **(Future) `learned`**: Could use a small classifier or LLM call.

---

## 2. Evaluation Harness

You can evaluate the current routing configuration against a labeled dataset.

### 2.1. Dataset Format

Create a JSON Lines (JSONL) file with test cases:

```jsonl
{"id": "1", "query": "Why is SKU W-44910 failing?", "expected_route": "erp", "relevant_slice_ids": ["slice_erp_123"]}
{"id": "2", "query": "How does the router work?", "expected_route": "docs"}
{"id": "3", "query": "def foo(x): return x", "expected_route": "code"}
```

Fields:
- `query`: The text to route/search.
- `expected_route`: (Optional) The route name you expect (`docs`, `code`, `erp`).
- `relevant_slice_ids`: (Optional) List of `span_hash` IDs that should appear in retrieval results.

### 2.2. Running Evaluation

Use the CLI command:

```bash
llmc routing eval --dataset path/to/eval.jsonl --top-k 10
```

Output example:

```text
=== Routing Evaluation Results ===
Total Examples:     50
Routing Accuracy:   92.00%
Retrieval Hit@10:   85.00%
Retrieval MRR:      0.7500
```

To get raw JSON output (for CI/CD):

```bash
llmc routing eval --dataset eval.jsonl --json
```

---

## 3. Workflow for Improvement

1. **Collect Failure Cases**: Save queries that were routed incorrectly or returned poor results.
2. **Add to Dataset**: Add them to `routing_eval.jsonl` with the correct expected route and relevant slice IDs.
3. **Run Eval**: Measure current baseline.
4. **Tune Config/Heuristics**:
   - Adjust `ERP_KEYWORDS`, `CODE_STRUCT_REGEX`, or multi-route weights in `llmc.toml`.
5. **Verify**: Run eval again to ensure metrics improved without regression.
