
import multiprocessing
import time

import pytest

from llmc.docgen.locks import DocgenLock


def hold_lock(repo_root, duration):
    # If time.sleep is patched by pytest-ruthless (which propagates to child processes via fork),
    # try to restore the original sleep function stashed by the plugin.
    if hasattr(time, "_original_sleep"):
        time.sleep = time._original_sleep

    lock = DocgenLock(repo_root)
    if lock.acquire():
        time.sleep(duration)
        lock.release()
        return True
    return False

def test_lock_acquisition(tmp_path):
    lock = DocgenLock(tmp_path)
    assert lock.acquire()
    lock.release()

@pytest.mark.allow_sleep
def test_lock_contention_fail(tmp_path):
    # Start a process that holds the lock for 2 seconds
    p = multiprocessing.Process(target=hold_lock, args=(tmp_path, 2))
    p.start()
    
    # Give it a moment to acquire
    time.sleep(0.5)
    
    lock = DocgenLock(tmp_path)
    # Try to acquire with 0 timeout -> fail
    assert not lock.acquire(timeout=0)
    
    # Try to acquire with 1s timeout -> fail (since holder holds for 2s)
    start = time.time()
    assert not lock.acquire(timeout=0.5)
    duration = time.time() - start
    assert duration >= 0.5 # Should have waited at least 0.5s
    
    p.join()

@pytest.mark.allow_sleep
def test_lock_contention_succeed(tmp_path):
    # Start a process that holds the lock for 1 second
    p = multiprocessing.Process(target=hold_lock, args=(tmp_path, 1))
    p.start()
    
    # Give it a moment to acquire
    time.sleep(0.2)
    
    lock = DocgenLock(tmp_path)
    # Try to acquire with 2s timeout -> succeed
    time.time()
    assert lock.acquire(timeout=2.0)
    lock.release()
    
    p.join()

def test_hold_lock_without_marker(tmp_path):
    # Regression test: Ensure hold_lock works even if the test itself
    # restricts sleep (e.g. absent marker). The child inherits the restriction
    # but hold_lock should now be able to unpatch it.
    p = multiprocessing.Process(target=hold_lock, args=(tmp_path, 0.1))
    p.start()
    p.join()
    assert p.exitcode == 0
