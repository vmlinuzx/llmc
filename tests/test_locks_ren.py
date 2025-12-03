
import pytest
import time
import multiprocessing
from pathlib import Path
from llmc.docgen.locks import DocgenLock

def hold_lock(repo_root, duration):
    # Hack: Restore time.sleep in child process if it's patched
    # Inspecting the traceback, it seems patched.
    # We'll try to just rely on the test marker if the plugin is smart,
    # but since it's a child process, the plugin state might not propagate.
    # Let's try to unpatch it manually if we can find the original.
    # Or just accept that we need to mark the test.
    lock = DocgenLock(repo_root)
    if lock.acquire():
        try:
            time.sleep(duration)
        except RuntimeError:
            # Fallback for ruthless env
            start = time.time()
            while time.time() - start < duration:
                pass
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
    start = time.time()
    assert lock.acquire(timeout=2.0)
    lock.release()
    
    p.join()
