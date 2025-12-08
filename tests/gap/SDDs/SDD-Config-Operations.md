# SDD: ChainOperations Logic & Safety

## 1. Gap Description
The `ChainOperations` class in `llmc/config/operations.py` manages CRUD operations for enrichment chains. It has several potential logical flaws and missing safeguards:
- **Shallow Copy**: `duplicate_chain` performs a shallow copy (`dict(source_chain)`). If chain configurations contain nested mutable objects (e.g., specific model parameters), modifying the duplicate could unintentionally affect the original.
- **Tier Sorting Defaults**: `get_cascade_order` defaults unknown tiers to a low priority (or high index), but this behavior isn't explicitly tested.
- **Deletion Safety**: `delete_chain` prevents deletion if a chain is the *only* one in a group referenced by a route. However, it doesn't check if the *remaining* siblings are actually enabled. If I delete the only *active* chain, the route effectively breaks.

## 2. Target Location
`tests/gap/test_config_operations.py`

## 3. Test Strategy
Unit tests for `ChainOperations` using specific test data.

### Scenarios to Test:
1.  **Deep Copy Verification**: 
    - Create a chain with nested data (e.g., `{"parameters": {"temp": 0.7}}`).
    - Duplicate it.
    - Modify the nested data in the new chain.
    - Assert the old chain is **unchanged**. (This test is expected to FAIL with current implementation).
2.  **Tier Sorting**:
    - Create a list of chains with mixed known ("nano", "70b") and unknown ("custom-8b") tiers.
    - Verify `get_cascade_order` sorts them correctly (custom tiers should probably be last).
3.  **Safe Deletion Logic**:
    - Scenario A: Chain is unique in group, used by route → Delete blocked.
    - Scenario B: Chain has siblings, but all siblings are `enabled=False` → Delete should probably warn or block (check current behavior).
    - Scenario C: Chain is not used by any route → Delete allowed.

## 4. Implementation Details
- Use `pytest`.
- Instantiate `ChainOperations` with a dict representing `llmc.toml`.
- Focus on the *logic* of the operations, not file I/O.
