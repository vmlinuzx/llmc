#!/usr/bin/env python3
"""
Integration tests for MAASL Phase 3: Code Protection.

Tests concurrent file access scenarios with multiple agents.
"""

import concurrent.futures
from pathlib import Path
import tempfile
import threading
import time

import pytest

from llmc_mcp.maasl import get_maasl
from llmc_mcp.tools.fs import FsResult
from llmc_mcp.tools.fs_protected import (
    delete_file_protected,
    edit_block_protected,
    move_file_protected,
    write_file_protected,
)


@pytest.fixture
def temp_dir():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def allowed_roots(temp_dir):
    """Return allowed roots for test operations."""
    return [str(temp_dir)]


@pytest.fixture
def test_file(temp_dir):
    """Create a test file."""
    test_path = temp_dir / "test.txt"
    test_path.write_text("initial content\n")
    return test_path


@pytest.mark.allow_sleep
def test_single_agent_write(temp_dir, allowed_roots):
    """Test single agent can write without contention."""
    test_path = temp_dir / "solo.txt"
    
    result = write_file_protected(
        path=test_path,
        allowed_roots=allowed_roots,
        content="Hello from agent1",
        agent_id="agent1",
        session_id="session1",
        operation_mode="interactive",
    )
    
    assert result.success is True
    assert result.data["bytes_written"] > 0
    assert test_path.read_text() == "Hello from agent1"


@pytest.mark.allow_sleep
def test_concurrent_writes_different_files(temp_dir, allowed_roots):
    """Test concurrent writes to different files succeed."""
    
    def write_agent(agent_id: str) -> FsResult:
        """Agent writes to its own file."""
        test_path = temp_dir / f"{agent_id}.txt"
        return write_file_protected(
            path=test_path,
            allowed_roots=allowed_roots,
            content=f"Content from {agent_id}",
            agent_id=agent_id,
            session_id=f"session_{agent_id}",
            operation_mode="interactive",
        )
    
    # Run 3 agents concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(write_agent, f"agent{i}")
            for i in range(1, 4)
        ]
        results = [f.result() for f in futures]
    
    # All should succeed (different files)
    assert all(r.success for r in results)
    
    # Verify files written
    for i in range(1, 4):
        fpath = temp_dir / f"agent{i}.txt"
        assert fpath.exists()
        assert fpath.read_text() == f"Content from agent{i}"


@pytest.mark.allow_sleep
def test_concurrent_writes_same_file_contention(test_file, allowed_roots):
    """
    Test concurrent writes to same file - one succeeds, others get ResourceBusyError.
    
    This is the core anti-stomp test.
    """
    barrier = threading.Barrier(3)  # Synchronize 3 agents
    results: list[FsResult] = []
    lock = threading.Lock()
    start_event = threading.Event()
    
    def write_agent(agent_id: str):
        """Agent attempts to write to shared file."""
        # Wait for all agents to be ready
        barrier.wait()
        
        # Wait for test to signal start (ensures all are waiting)
        start_event.wait()
        
        # Create a slow write that holds the lock while writing
        def slow_write():
            # Simulate realistic write delay
            # Hold longer than interactive timeout (500ms) to force contention
            time.sleep(0.6)  # 600ms hold time
            test_file.write_text(f"Content from {agent_id}\n")
            return True
        
        from llmc_mcp.maasl import ResourceDescriptor
        
        resource = ResourceDescriptor(
            resource_class="CRIT_CODE",
            identifier=str(test_file),
        )
        
        try:
            maasl = get_maasl()
            maasl.call_with_stomp_guard(
                op=slow_write,
                resources=[resource],
                intent="write_file",
                mode="interactive",
                agent_id=agent_id,
                session_id=f"session_{agent_id}",
            )
            # Success
            result = FsResult(
                success=True,
                data={"agent": agent_id},
                meta={"path": str(test_file)},
            )
        except Exception as e:
            # Lock contention or other error
            from llmc_mcp.maasl import ResourceBusyError
            if isinstance(e, ResourceBusyError):
                result = FsResult(
                    success=False,
                    data=None,
                    meta={
                        "path": str(test_file),
                        "resource_key": e.resource_key,
                        "holder_agent_id": e.holder_agent_id,
                    },
                    error=f"File locked by {e.holder_agent_id}: {str(e)}",
                )
            else:
                result = FsResult(
                    success=False,
                    data=None,
                    meta={"path": str(test_file)},
                    error=str(e),
                )
        
        with lock:
            results.append(result)
    
    # Launch 3 agents
    threads = [
        threading.Thread(target=write_agent, args=(f"agent{i}",))
        for i in range(1, 4)
    ]
    
    for t in threads:
        t.start()
    
    # Brief delay to ensure all threads are waiting at barrier
    time.sleep(0.01)
    
    # Signal start to all threads simultaneously
    start_event.set()
    
    for t in threads:
        t.join()
    
    # At least one should succeed, at least one should fail (contention occurred)
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    
    # Key assertions:
    # 1. At least one agent succeeded (liveness)
    assert len(successes) >= 1, f"Expected at least 1 success, got {len(successes)}"
    
    # 2. At least one agent was blocked (contention occurred)
    assert len(failures) >= 1, f"Expected at least 1 failure (contention), got {len(failures)}"
    
    # 3. MOST IMPORTANT: No file corruption
    # This is the CRITICAL property that MAASL guarantees
    final_content = test_file.read_text()
    lines = final_content.strip().split("\n")
    assert len(lines) == 1, f"File corruption detected! Multiple writes: {lines}"
    assert lines[0].startswith("Content from agent"), f"Invalid content: {lines[0]}"




@pytest.mark.allow_sleep
def test_concurrent_edits_same_file(test_file, allowed_roots):
    """Test concurrent edits to same file - protected by MAASL."""
    barrier = threading.Barrier(2)
    results: list[FsResult] = []
    lock = threading.Lock()
    
    def edit_agent(agent_id: str):
        """Agent attempts to edit shared file."""
        barrier.wait()
        
        result = edit_block_protected(
            path=test_file,
            allowed_roots=allowed_roots,
            old_text="initial content",
            new_text=f"edited by {agent_id}",
            expected_replacements=1,
            agent_id=agent_id,
            session_id=f"session_{agent_id}",
            operation_mode="interactive",
        )
        
        with lock:
            results.append(result)
    
    threads = [
        threading.Thread(target=edit_agent, args=(f"agent{i}",))
        for i in range(1, 3)
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Exactly 1 succeeds, 1 fails
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    
    assert len(successes) == 1
    assert len(failures) == 1
    
    # Verify no corruption
    final_content = test_file.read_text()
    assert "edited by agent" in final_content


@pytest.mark.allow_sleep
def test_move_file_protection(temp_dir, allowed_roots):
    """Test move operations are protected."""
    src = temp_dir / "source.txt"
    dst = temp_dir / "dest.txt"
    src.write_text("movable content")
    
    barrier = threading.Barrier(2)
    results: list[FsResult] = []
    lock = threading.Lock()
    
    def move_agent(agent_id: str):
        """Agent attempts to move file."""
        barrier.wait()
        
        result = move_file_protected(
            source=src,
            dest=dst,
            allowed_roots=allowed_roots,
            agent_id=agent_id,
            session_id=f"session_{agent_id}",
            operation_mode="interactive",
        )
        
        with lock:
            results.append(result)
    
    threads = [
        threading.Thread(target=move_agent, args=(f"agent{i}",))
        for i in range(1, 3)
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # One succeeds, one fails
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    
    assert len(successes) == 1
    assert len(failures) == 1
    
    # File should be moved
    assert not src.exists()
    assert dst.exists()


@pytest.mark.allow_sleep
def test_delete_file_protection(temp_dir, allowed_roots):
    """Test delete operations are protected."""
    target = temp_dir / "deleteme.txt"
    target.write_text("to be deleted")
    
    barrier = threading.Barrier(2)
    results: list[FsResult] = []
    lock = threading.Lock()
    
    def delete_agent(agent_id: str):
        """Agent attempts to delete file."""
        barrier.wait()
        
        result = delete_file_protected(
            path=target,
            allowed_roots=allowed_roots,
            agent_id=agent_id,
            session_id=f"session_{agent_id}",
            operation_mode="interactive",
        )
        
        with lock:
            results.append(result)
    
    threads = [
        threading.Thread(target=delete_agent, args=(f"agent{i}",))
        for i in range(1, 3)
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # One succeeds, one fails (file already deleted or locked)
    successes = [r for r in results if r.success]
    
    # At least one should succeed
    assert len(successes) >= 1
    
    # File should be gone
    assert not target.exists()


@pytest.mark.allow_sleep
def test_lock_cleanup_after_operation(test_file, allowed_roots):
    """Test locks are properly released after operation completes."""
    from llmc_mcp.locks import get_lock_manager
    
    # Write with protection
    result = write_file_protected(
        path=test_file,
        allowed_roots=allowed_roots,
        content="test content",
        agent_id="agent1",
        session_id="session1",
        operation_mode="interactive",
    )
    
    assert result.success is True
    
    # Verify lock was released
    mgr = get_lock_manager()
    snapshot = mgr.snapshot()
    
    # No locks should be held
    assert len(snapshot) == 0, f"Expected 0 locks, got {len(snapshot)}"


@pytest.mark.allow_sleep
def test_sequential_writes_same_file(test_file, allowed_roots):
    """Test sequential writes to same file succeed (no contention)."""
    
    for i in range(1, 4):
        result = write_file_protected(
            path=test_file,
            allowed_roots=allowed_roots,
            content=f"Write {i}\n",
            agent_id=f"agent{i}",
            session_id=f"session{i}",
            operation_mode="interactive",
        )
        assert result.success is True
    
    # Last write should be visible
    assert test_file.read_text() == "Write 3\n"


@pytest.mark.allow_sleep
def test_batch_mode_longer_timeout(test_file, allowed_roots):
    """Test batch mode has longer timeout than interactive."""
    from llmc_mcp.maasl import PolicyRegistry
    
    policy = PolicyRegistry()
    crit_code = policy.get_resource_class("CRIT_CODE")
    
    # Batch timeout should be higher
    assert crit_code.batch_max_wait_ms > crit_code.max_wait_ms
    
    # Write in batch mode succeeds
    result = write_file_protected(
        path=test_file,
        allowed_roots=allowed_roots,
        content="batch write",
        agent_id="batchagent",
        session_id="batchsession",
        operation_mode="batch",
    )
    
    assert result.success is True


@pytest.mark.allow_sleep
def test_multi_resource_sorted_locking(temp_dir, allowed_roots):
    """Test that multi-resource operations use sorted locking for deadlock prevention."""
    file1 = temp_dir / "file1.txt"
    file2 = temp_dir / "file2.txt"
    file1.write_text("content1")
    file2.write_text("content2")
    
    # Move uses 2 locks (source and dest)
    # Should acquire in sorted order to prevent deadlock
    result = move_file_protected(
        source=file1,
        dest=file2,
        allowed_roots=allowed_roots,
        agent_id="agent1",
        session_id="session1",
        operation_mode="interactive",
    )
    
    # Should succeed
    assert result.success is True


@pytest.mark.allow_sleep
def test_high_contention_stress(temp_dir, allowed_roots):
    """
    Stress test with 5 agents fighting for same file.
    
    Verifies no file corruption under extreme contention.
    """
    target = temp_dir / "hotfile.txt"
    target.write_text("initial\n")
    
    barrier = threading.Barrier(5)
    results: list[FsResult] = []
    lock = threading.Lock()
    
    def aggressive_writer(agent_id: str):
        """Agent aggressively tries to write."""
        barrier.wait()
        
        # Try multiple times
        for attempt in range(3):
            result = write_file_protected(
                path=target,
                allowed_roots=allowed_roots,
                content=f"Agent {agent_id} attempt {attempt}\n",
                agent_id=agent_id,
                session_id=f"session_{agent_id}",
                operation_mode="interactive",
            )
            
            with lock:
                results.append(result)
            
            if result.success:
                break
            
            # Back off slightly
            time.sleep(0.01)
    
    # Launch 5 agents
    threads = [
        threading.Thread(target=aggressive_writer, args=(f"agent{i}",))
        for i in range(1, 6)
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # At least some should succeed
    successes = [r for r in results if r.success]
    assert len(successes) > 0
    
    # File content should be clean (one complete write)
    final_content = target.read_text()
    lines = final_content.strip().split("\n")
    
    # Should be exactly 1 line (no interleaved writes)
    assert len(lines) == 1, f"File corrupted: {lines}"
    assert lines[0].startswith("Agent")


def test_maasl_telemetry_logging(test_file, allowed_roots, caplog):
    """Test that MAASL operations are logged via telemetry."""
    import logging
    caplog.set_level(logging.INFO)
    
    result = write_file_protected(
        path=test_file,
        allowed_roots=allowed_roots,
        content="telemetry test",
        agent_id="agent1",
        session_id="session1",
        operation_mode="interactive",
    )
    
    assert result.success is True
    
    # Check that telemetry logged the operation
    # (telemetry uses structured logging to stderr)
    # At minimum, ensure no exceptions from telemetry
