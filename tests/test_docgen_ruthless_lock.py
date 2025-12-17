from unittest.mock import patch

from llmc.docgen.locks import DocgenLock


def test_docgen_lock_leak_on_timeout(tmp_path):
    """Verify that DocgenLock leaks a file handle if acquire times out."""
    repo_root = tmp_path
    llmc_dir = repo_root / ".llmc"
    llmc_dir.mkdir()

    lock = DocgenLock(repo_root, timeout=0.1)

    # Mock fcntl.flock to always raise BlockingIOError
    # Mock time.sleep to do nothing (avoid delay and avoid strict test restrictions)
    # Mock time.time to control the loop
    with (
        patch("fcntl.flock", side_effect=BlockingIOError),
        patch("time.sleep", return_value=None),
        patch("time.time", side_effect=[100, 100.05, 100.2]),
    ):  # Start, loop check, end

        acquired = lock.acquire()

        assert acquired is False, "Should fail to acquire lock"

        # Check if file handle is still open
        assert lock._lock_handle is not None, "File handle should be set (leak)"
        assert not lock._lock_handle.closed, "File handle should be open (leak)"

        # Cleanup if it leaked (manual cleanup to be nice)
        if lock._lock_handle:
            lock._lock_handle.close()


def test_docgen_lock_no_leak_on_immediate_fail(tmp_path):
    """Verify that DocgenLock does NOT leak if timeout is 0."""
    repo_root = tmp_path
    llmc_dir = repo_root / ".llmc"
    llmc_dir.mkdir()

    lock = DocgenLock(repo_root, timeout=0)

    # Mock fcntl.flock to raise BlockingIOError
    with patch("fcntl.flock", side_effect=BlockingIOError):
        acquired = lock.acquire()

        assert acquired is False

        # Check if file handle is closed/None
        assert lock._lock_handle is None, "File handle should be cleaned up"
