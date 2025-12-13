# SDD: Router Resilience

## 1. Gap Description
The `classify_query` function in `llmc/routing/query_type.py` calls external heuristic modules (`code_heuristics.score_all`, `erp_heuristics.score_all`) without error handling. If these modules raise an unhandled exception (e.g., regex error, malformed input), the entire routing process crashes. A robust system should catch these errors, log them, and fall back to a default route.

## 2. Target Location
`tests/gap/test_router_resilience.py`

## 3. Test Strategy
1.  **Mocking**: Use `unittest.mock.patch` to replace `llmc.routing.code_heuristics.score_all` with a mock that raises `ValueError("Simulated failure")`.
2.  **Execution**: Call `classify_query("some query")`.
3.  **Assertion**:
    *   The function should NOT raise an exception.
    *   The return value should be the default route (`{"route_name": "docs", ...}`).
    *   (Optional) Verify logging if possible, but return value is key.

## 4. Implementation Details
- Use `pytest`.
- Import `classify_query` from `llmc.routing.query_type`.
- Use `patch("llmc.routing.code_heuristics.score_all", side_effect=ValueError("Boom"))`.
- Verify that `classify_query` handles this gracefully (i.e., the test expects the function to catch the error).
- **Note:** Since the current code *does not* catch the error, this test is EXPECTED TO FAIL. This confirms the gap.
