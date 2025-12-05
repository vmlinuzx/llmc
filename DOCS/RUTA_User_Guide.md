# RUTA User Guide (Ruthless User Testing Agent)

RUTA is an automated testing framework that simulates end-user interactions with the LLMC system. It uses "User Executor" agents to perform tasks via real interfaces (CLI, MCP, etc.) and "Judge" agents to evaluate the results against strict properties and metamorphic relations.

## Quick Start

Run the "search model bug" regression test:

```bash
python3 -m llmc.main usertest run tests/usertests/search_model_bug.yaml
```

## Concepts

### 1. Scenarios (`.yaml`)
Scenarios define what the user wants to achieve and what the system should do. They live in `tests/usertests/`.

Example `tests/usertests/example.yaml`:
```yaml
id: example_scenario
description: Verify search works
goal: Find documentation about routing
queries:
  base: "routing"

expectations:
  must_use_tools:
    - rag_search
  properties:
    - name: search_returns_results
      type: metamorphic
      constraint: result_count("routing") > 0
```

### 2. Properties
Properties define the success criteria.

*   **Assertion**: Simple checks on tool success.
    ```yaml
    - name: success
      type: assertion
      constraint: result.success == true
    ```

*   **Metamorphic**: Checks relationships between inputs and outputs.
    ```yaml
    - name: stable_results
      type: metamorphic
      relation: result_count("A") == result_count("A")
      constraint: result_count("A") > 0
    ```

### 3. Metamorphic DSL
The following functions are available in `constraint` and `relation` fields:

*   `result_count(query)`: Returns the number of hits for the last `rag_search` with the given query.
*   `results(query)`: Returns a set of item IDs (paths) for the last `rag_search` with the given query.
*   `jaccard(set1, set2)`: Calculates Jaccard similarity between two sets.
    *   Example: `jaccard(results("A B"), results("B A")) >= 0.9`

## Running Tests

Use the `llmc usertest` command:

```bash
# Run a specific scenario file
python3 -m llmc.main usertest run tests/usertests/my_scenario.yaml

# Run all scenarios in a directory (coming soon)
# python3 -m llmc.main usertest run tests/usertests/
```

## Reports

After a run, artifacts are saved to `artifacts/ruta/`:
*   `trace_*.jsonl`: Detailed log of every step, tool call, and thought.
*   `report_*.json`: Summary of pass/fail status and incidents.

## Troubleshooting

If a test fails:
1.  Check the report JSON for the specific incident ID and details.
2.  Inspect the trace JSONL to see the agent's thoughts and tool outputs.
3.  Verify the system state (e.g., is the RAG index built?).
