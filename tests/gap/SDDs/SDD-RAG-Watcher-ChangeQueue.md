# SDD: RAG Watcher ChangeQueue Coverage

## 1. Gap Description
The `ChangeQueue` class in `llmc/rag/watcher.py` handles debouncing of file change events for the RAG service. It is critical for preventing index thrashing. Currently, there are no tests for this class. Specifically, the debounce logic, the potential for starvation (continuous updates preventing processing), and basic thread safety (locking) are unverified.

## 2. Target Location
`tests/rag/test_watcher_queue.py`

## 3. Test Strategy
We will use unit tests with `unittest.mock.patch` to control `time.time`.
- **Debounce Logic:** Verify that `get_ready()` returns nothing before `debounce_seconds` have passed, and returns the item after.
- **Starvation:** Verify that continuous `add()` calls reset the timer, preventing `get_ready()` from returning the item (confirming the current behavior, even if it's a "bug", we need to test the *behavior*).
- **Thread Safety:** Use `threading.Thread` to simulate concurrent `add()` calls and verify `has_pending()` and `get_ready()` state remains consistent.
- **Wait/Clear:** Verify `wait()` blocks/unblocks correctly and `clear()` removes pending items.

## 4. Implementation Details
- Use `pytest`.
- Use `unittest.mock.patch("time.time")` to simulate time passing.
- Implement `test_debounce_basic`: Add item, check not ready, advance time, check ready.
- Implement `test_starvation`: Add item, advance time slightly (less than debounce), add item again, advance time (total > debounce but time-since-last < debounce), check not ready.
- Implement `test_concurrent_adds`: Spawn threads to add items, verify all are tracked (or last update wins).
- Implement `test_wait_timeout`: Verify `wait()` respects timeout.
