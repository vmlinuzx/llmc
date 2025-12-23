# SDD: RAG Client - Invalid Lineage Direction

## 1. Gap Description

The `RAGClient.lineage` method, which calls the underlying `tool_rag_lineage` function, does not handle invalid input for the `direction` parameter. The `tool_rag_lineage` function silently defaults any invalid direction to `'downstream'` instead of raising an error.

This is a weakness in the API contract. A user providing an invalid direction (e.g., 'sideways') should be notified with an error, not receive misleading 'downstream' results. This test will codify the current, non-ideal behavior.

## 2. Target Location

A **new test file** shall be created at: `tests/test_rag_client.py`

## 3. Test Strategy

The test will focus on the `RAGClient` facade. It will use `unittest.mock.patch` to "spy" on the underlying `tool_rag_lineage` function. This allows us to assert that the client correctly passes arguments to the tool handler and to confirm how the handler is called when the input is invalid.

## 4. Implementation Details

The new test file must contain the following test case:

1.  **`test_lineage_with_invalid_direction_defaults_to_downstream`**:
    -   Import `RAGClient` from `llmc.client` and `tool_rag_lineage` from `llmc.rag_nav.tool_handlers`.
    -   Use `@patch('llmc.client.tool_rag_lineage')` to mock the tool handler.
    -   Inside the test, instantiate `RAGClient`.
    -   Call `client.lineage(symbol='foo', direction='sideways')`.
    -   Assert that the mocked `tool_rag_lineage` was called exactly once.
    -   Check the arguments passed to the mock. Assert that the `direction` argument it received was `'sideways'`, demonstrating the client passes it through. The test implicitly verifies the underlying tool handler's default behavior, which is the subject of this gap.

    *Note to implementer:* This test verifies the current behavior. A follow-up improvement would be to modify the source code to raise a `ValueError` for an invalid direction and update this test to assert that `pytest.raises(ValueError)` is triggered.
