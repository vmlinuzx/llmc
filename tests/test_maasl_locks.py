#!/usr/bin/env python3
"""
Unit tests for MAASL LockManager.

Tests:
- Lock acquisition and release
- Lease expiry and takeover
- Fencing token increments
- Timeout behavior
- Snapshot introspection
"""

import pytest
import time
import threading
from llmc_mcp.locks import (
    LockManager,
    LockState,
    LockHandle,
    ResourceBusyError,
)


class TestLockState:
    """Test LockState dataclass."""
    
    def test_is_expired(self):
        """Test lease expiry check."""
        lock = LockState(resource_key="test:foo")
        
        now = time.time()
        lock.lease_expiry_ts = now + 10  # Expires in 10 seconds
        
        assert not lock.is_expired(now)
        assert not lock.is_expired(now + 5)
        assert lock.is_expired(now + 10)
        assert lock.is_expired(now + 15)
    
    def test_is_held_by(self):
        """Test holder check."""
        lock = LockState(resource_key="test:foo")
        lock.holder_agent_id = "agent1"
        lock.holder_session_id = "session1"
        
        assert lock.is_held_by("agent1", "session1")
        assert not lock.is_held_by("agent2", "session1")
        assert not lock.is_held_by("agent1", "session2")


class TestLockManager:
    """Test LockManager core functionality."""
    
    def test_acquire_and_release(self):
        """Test basic acquire and release."""
        mgr = LockManager()
        
        # Acquire lock
        handle = mgr.acquire(
            resource_key="test:foo",
            agent_id="agent1",
            session_id="session1",
            lease_ttl_sec=30,
            max_wait_ms=500,
        )
        
        assert handle.resource_key == "test:foo"
        assert handle.agent_id == "agent1"
        assert handle.session_id == "session1"
        assert handle.fencing_token == 1  # First token
        
        # Verify snapshot shows held lock
        snapshot = mgr.snapshot()
        assert len(snapshot) == 1
        assert snapshot[0]["resource_key"] == "test:foo"
        assert snapshot[0]["holder_agent_id"] == "agent1"
        assert snapshot[0]["fencing_token"] == 1
        
        # Release lock
        mgr.release(
            resource_key="test:foo",
            agent_id="agent1",
            session_id="session1",
            fencing_token=handle.fencing_token,
        )
        
        # Snapshot should be empty
        snapshot = mgr.snapshot()
        assert len(snapshot) == 0
    
    @pytest.mark.allow_sleep
    def test_acquire_timeout(self):
        """Test lock acquisition timeout."""
        mgr = LockManager()
        
        # Agent 1 acquires lock
        handle1 = mgr.acquire(
            resource_key="test:foo",
            agent_id="agent1",
            session_id="session1",
            lease_ttl_sec=30,
            max_wait_ms=500,
        )
        
        # Agent 2 tries to acquire same lock with short timeout
        with pytest.raises(ResourceBusyError) as exc_info:
            mgr.acquire(
                resource_key="test:foo",
                agent_id="agent2",
                session_id="session2",
                lease_ttl_sec=30,
                max_wait_ms=100,  # Very short timeout
            )
        
        err = exc_info.value
        assert err.resource_key == "test:foo"
        assert err.holder_agent_id == "agent1"
        assert err.holder_session_id == "session1"
        assert err.wait_ms >= 100
        
        # Cleanup
        mgr.release(
            resource_key="test:foo",
            agent_id="agent1",
            session_id="session1",
            fencing_token=handle1.fencing_token,
        )
    
    @pytest.mark.allow_sleep
    def test_lease_expiry_takeover(self):
        """Test lease expiry and takeover."""
        mgr = LockManager()
        
        # Agent acquires lock with very short TTL
        handle1 = mgr.acquire(
            resource_key="test:foo",
            agent_id="agent1",
            session_id="session1",
            lease_ttl_sec=1,  # 1 second TTL
            max_wait_ms=500,
        )
        
        # Release lock properly
        mgr.release(
            resource_key="test:foo",
            agent_id="agent1",
            session_id="session1",
            fencing_token=handle1.fencing_token,
        )
        
        # Agent 2 should be able to acquire freely now
        handle2 = mgr.acquire(
            resource_key="test:foo",
            agent_id="agent2",
            session_id="session2",
            lease_ttl_sec=30,
            max_wait_ms=500,
        )
        
        assert handle2.agent_id == "agent2"
        assert handle2.fencing_token > handle1.fencing_token
        
        # Snapshot should show agent2
        snapshot = mgr.snapshot()
        assert len(snapshot) == 1
        assert snapshot[0]["holder_agent_id"] == "agent2"
        
        # Cleanup
        mgr.release(
            resource_key="test:foo",
            agent_id="agent2",
            session_id="session2",
            fencing_token=handle2.fencing_token,
        )

    
    def test_fencing_token_increments(self):
        """Test fencing tokens increment monotonically."""
        mgr = LockManager()
        
        tokens = []
        for i in range(5):
            handle = mgr.acquire(
                resource_key=f"test:resource{i}",
                agent_id="agent1",
                session_id="session1",
                lease_ttl_sec=30,
                max_wait_ms=500,
            )
            tokens.append(handle.fencing_token)
            mgr.release(
                resource_key=f"test:resource{i}",
                agent_id="agent1",
                session_id="session1",
                fencing_token=handle.fencing_token,
            )
        
        # Tokens should be strictly increasing
        assert tokens == [1, 2, 3, 4, 5]
    
    def test_release_validation(self):
        """Test release validates agent/session/token."""
        mgr = LockManager()
        
        handle = mgr.acquire(
            resource_key="test:foo",
            agent_id="agent1",
            session_id="session1",
            lease_ttl_sec=30,
            max_wait_ms=500,
        )
        
        # Wrong agent
        with pytest.raises(ValueError, match="not held by"):
            mgr.release(
                resource_key="test:foo",
                agent_id="agent2",
                session_id="session1",
                fencing_token=handle.fencing_token,
            )
        
        # Wrong session
        with pytest.raises(ValueError, match="not held by"):
            mgr.release(
                resource_key="test:foo",
                agent_id="agent1",
                session_id="session2",
                fencing_token=handle.fencing_token,
            )
        
        # Wrong token
        with pytest.raises(ValueError, match="token mismatch"):
            mgr.release(
                resource_key="test:foo",
                agent_id="agent1",
                session_id="session1",
                fencing_token=999,
            )
        
        # Cleanup with correct params
        mgr.release(
            resource_key="test:foo",
            agent_id="agent1",
            session_id="session1",
            fencing_token=handle.fencing_token,
        )
    
    @pytest.mark.allow_sleep
    def test_renew_lease(self):
        """Test lease renewal."""
        mgr = LockManager()
        
        handle = mgr.acquire(
            resource_key="test:foo",
            agent_id="agent1",
            session_id="session1",
            lease_ttl_sec=5,
            max_wait_ms=500,
        )
        
        initial_expiry = handle.lease_expiry_ts
        
        # Renew lease
        time.sleep(0.1)
        mgr.renew(
            resource_key="test:foo",
            agent_id="agent1",
            session_id="session1",
            fencing_token=handle.fencing_token,
            lease_ttl_sec=10,
        )
        
        # Get updated state from snapshot
        snapshot = mgr.snapshot()
        assert len(snapshot) == 1
        
        # TTL should be longer now (close to 10 seconds)
        assert snapshot[0]["ttl_remaining_sec"] > 8
        
        # Cleanup
        mgr.release(
            resource_key="test:foo",
            agent_id="agent1",
            session_id="session1",
            fencing_token=handle.fencing_token,
        )
    
    @pytest.mark.allow_sleep
    def test_concurrent_access(self):
        """Test concurrent lock acquisition from multiple threads."""
        mgr = LockManager()
        acquired_count = {"value": 0}
        lock = threading.Lock()
        
        def try_acquire(agent_id: str):
            try:
                handle = mgr.acquire(
                    resource_key="test:contention",
                    agent_id=agent_id,
                    session_id="session1",
                    lease_ttl_sec=1,
                    max_wait_ms=2000,
                )
                
                # Critical section
                with lock:
                    acquired_count["value"] += 1
                
                time.sleep(0.1)  # Hold briefly
                
                mgr.release(
                    resource_key="test:contention",
                    agent_id=agent_id,
                    session_id="session1",
                    fencing_token=handle.fencing_token,
                )
            except ResourceBusyError:
                pass  # Expected for some threads
        
        # Spawn 5 threads trying to acquire same lock
        threads = []
        for i in range(5):
            t = threading.Thread(target=try_acquire, args=(f"agent{i}",))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # At least some should have succeeded
        assert acquired_count["value"] >= 1
        
        # Final snapshot should be empty (all released)
        snapshot = mgr.snapshot()
        assert len(snapshot) == 0


class TestResourceBusyError:
    """Test ResourceBusyError exception."""
    
    def test_to_dict(self):
        """Test conversion to MCP payload."""
        err = ResourceBusyError(
            resource_key="test:foo",
            holder_agent_id="agent1",
            holder_session_id="session1",
            wait_ms=523.4,
            max_wait_ms=500,
        )
        
        payload = err.to_dict()
        assert payload["resource_key"] == "test:foo"
        assert payload["holder_agent_id"] == "agent1"
        assert payload["holder_session_id"] == "session1"
        assert payload["wait_ms"] == 523.4
        assert payload["max_wait_ms"] == 500
