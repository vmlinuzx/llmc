# SDD: Missing Test Coverage for get_repo_stats Success Path

## 1. Gap Description
The function `llmc.cli.get_repo_stats` is tested for various failure modes, but there is no test case that verifies its behavior on a successful run. When its dependencies (`load_status`, `_load_graph`) return valid data, the function should correctly process that data and return a properly populated statistics dictionary.

## 2. Target Location
`tests/cli/test_cli.py`

## 3. Test Strategy
The test will use `unittest.mock.patch` to mock the `load_status` and `_load_graph` functions.

- **Mock `_load_graph`**: This should return a predefined list of mock nodes and an empty list for edges. The nodes should have a structure that `get_repo_stats` expects, including some nodes with and some without the 'summary' in their metadata to test the 'enriched_nodes' calculation.
- **Mock `load_status`**: This should return a mock status object with `index_state` and `last_indexed_at` attributes.
- **Assertion**: The test will call `get_repo_stats` and assert that the returned dictionary contains the correct values based on the mocked inputs. This includes checking `graph_nodes`, `enriched_nodes`, `freshness_state`, `last_indexed_at`, etc.

## 4. Implementation Details
Create a new test function `test_get_repo_stats_success(mock_repo_root)` in `tests/cli/test_cli.py`.

Inside the test function:
1. Define mock data for nodes. For example, two nodes, one with a 'summary' and one without.
2. Define a mock `IndexStatus` object.
3. Use `patch('llmc.cli._load_graph', return_value=(mock_nodes, []))`
4. Use `patch('llmc.cli.load_status', return_value=mock_index_status)`
5. Call `stats = get_repo_stats(mock_repo_root)`.
6. Assert `stats['error'] is None`.
7. Assert `stats['graph_nodes'] == 2`.
8. Assert `stats['enriched_nodes'] == 1`.
9. Assert `stats['freshness_state'] == 'FRESH'`.
10. Assert that `token_usage` is calculated correctly based on the summary length.

This will ensure the core logic of the function is working as intended under normal conditions.
