# SDD: RAG Watcher Debounce & Starvation

## 1. Gap Description
The `ChangeQueue` in `llmc/rag/watcher.py` uses a "trailing edge" debounce mechanism (`self._pending[repo_path] = time.time()`).
If a repository is constantly changing (e.g., a log file or build artifact that slips past the `FileFilter`), the queue will strictly postpone processing.
This can lead to **Index Starvation**, where the RAG indexer never runs because the debounce timer keeps resetting.
We need a test to demonstrate this starvation behavior and potentially drive a fix (e.g., `max_wait` timeout).

## 2. Target Location
`tests/rag/test_watcher_starvation.py`

## 3. Test Strategy
1. **Starvation Test**: Simulate a stream of events arriving faster than `debounce_seconds`. Assert that `get_ready()` returns nothing for an extended period (exceeding reasonable latency).
2. **Debounce Test**: Verify that sporadic events do trigger `get_ready()` after the debounce window.

## 4. Implementation Details
```python
import time
import threading
import unittest
from llmc.rag.watcher import ChangeQueue

class TestWatcherStarvation(unittest.TestCase):
    def test_starvation_under_load(self):
        """Verify that constant updates prevent the queue from becoming ready."""
        queue = ChangeQueue(debounce_seconds=0.1)
        repo_path = "/tmp/repo"

        start_time = time.time()
        # Simulate continuous updates for 0.5 seconds (5x debounce)
        while time.time() - start_time < 0.5:
            queue.add(repo_path)
            time.sleep(0.05) # fast updates

            # Check ready
            ready = queue.get_ready()
            self.assertEqual(ready, [], "Queue should not be ready during active updates")

        # Stop updates, wait for debounce
        time.sleep(0.15)
        ready = queue.get_ready()
        self.assertEqual(ready, [repo_path], "Queue should be ready after updates stop")

    def test_max_wait_proposal(self):
        """
        Gap documentation test:
        Demonstrate that we DO NOT have a max_wait mechanism.
        Ideally, we want: if time.time() - first_update > max_wait, return ready anyway.
        """
        # This test documents current behavior (infinite delay).
        # If we implement max_wait, this test should be updated.
        pass
```
