import threading
import time
from unittest.mock import patch
import pytest

from llmc.rag.watcher import ChangeQueue

class TestChangeQueue:
    def test_debounce_basic(self):
        """Test that items are not ready until debounce time passes."""
        queue = ChangeQueue(debounce_seconds=2.0)

        with patch("time.time") as mock_time:
            mock_time.return_value = 100.0
            queue.add("repo1")

            # Not ready immediately
            assert queue.get_ready() == []

            # Advance time to 101.0 (1s elapsed) - still not ready
            mock_time.return_value = 101.0
            assert queue.get_ready() == []

            # Advance time to 102.0 (2s elapsed) - ready!
            mock_time.return_value = 102.0
            ready = queue.get_ready()
            assert "repo1" in ready
            assert len(ready) == 1

            # Queue should be empty now
            assert queue.get_ready() == []

    def test_starvation(self):
        """
        Test that continuous updates extend the wait time (starvation).
        This confirms the current behavior where an item is never ready
        if it keeps getting updated.
        """
        queue = ChangeQueue(debounce_seconds=2.0)

        with patch("time.time") as mock_time:
            mock_time.return_value = 100.0
            queue.add("repo1")

            # Advance 1.5s
            mock_time.return_value = 101.5
            assert queue.get_ready() == []

            # Update again (reset timer)
            queue.add("repo1")

            # Advance another 1.5s (total 3.0s from start, but 1.5s from last update)
            mock_time.return_value = 103.0
            assert queue.get_ready() == []

            # Advance to 104.0 (2.5s from last update)
            mock_time.return_value = 104.0
            assert queue.get_ready() == ["repo1"]

    def test_wait_timeout(self):
        """Test wait timeout behavior."""
        queue = ChangeQueue(debounce_seconds=2.0)

        # Should return False on timeout
        start = time.time()
        result = queue.wait(timeout=0.1)
        end = time.time()

        assert result is False
        assert (end - start) >= 0.1

    def test_wait_success(self):
        """Test wait returns True when item added."""
        queue = ChangeQueue(debounce_seconds=2.0)

        def add_later():
            try:
                time.sleep(0.1)
            except RuntimeError:
                pass
            queue.add("repo1")

        t = threading.Thread(target=add_later)
        t.start()

        # We don't mock time.time here so we use real time for timeout
        result = queue.wait(timeout=1.0)
        t.join()

        assert result is True

    def test_clear(self):
        """Test clearing the queue."""
        queue = ChangeQueue(debounce_seconds=2.0)
        queue.add("repo1")
        assert queue.has_pending() is True

        queue.clear()
        assert queue.has_pending() is False
        assert queue.get_ready() == []

    def test_concurrent_adds(self):
        """Test thread safety with concurrent adds."""
        queue = ChangeQueue(debounce_seconds=2.0)
        repos = [f"repo{i}" for i in range(100)]

        def worker(repo):
            queue.add(repo)

        threads = [threading.Thread(target=worker, args=(r,)) for r in repos]

        with patch("time.time") as mock_time:
            mock_time.return_value = 100.0

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert queue.has_pending() is True

            # Advance time
            mock_time.return_value = 105.0
            ready = queue.get_ready()

            # All repos should be present
            assert len(ready) == 100
            assert set(ready) == set(repos)
