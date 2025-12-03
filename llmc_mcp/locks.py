#!/usr/bin/env python3
"""
MAASL Lock Manager - In-process locking with leases and fencing tokens.

Provides mutex-based resource locking with:
- Per-resource lock instances
- Lease TTL with expiry checking
- Fencing tokens (monotonic counter) to prevent ABA problems
- Deadlock prevention through sorted lock acquisition
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, List
import logging

from llmc_mcp.telemetry import get_telemetry_sink

logger = logging.getLogger("llmc-mcp.maasl.locks")


@dataclass
class LockState:
    """
    State for a single resource lock.
    
    Tracks current holder, lease expiry, and fencing token.
    """
    resource_key: str
    mutex: threading.Lock = field(default_factory=threading.Lock)
    holder_agent_id: Optional[str] = None
    holder_session_id: Optional[str] = None
    lease_expiry_ts: float = 0.0  # epoch seconds
    fencing_token: int = 0  # monotonic increasing
    acquired_at: float = 0.0  # epoch seconds when lock was acquired
    
    def is_expired(self, now: float) -> bool:
        """Check if current lease has expired."""
        return now >= self.lease_expiry_ts
    
    def is_held_by(self, agent_id: str, session_id: str) -> bool:
        """Check if lock is held by specific agent/session."""
        return (
            self.holder_agent_id == agent_id 
            and self.holder_session_id == session_id
        )


@dataclass
class LockHandle:
    """
    Handle returned on successful lock acquisition.
    
    Contains fencing token for verification on release.
    """
    resource_key: str
    agent_id: str
    session_id: str
    fencing_token: int
    acquired_at: float
    lease_expiry_ts: float


class LockManager:
    """
    In-process lock manager for MAASL resource coordination.
    
    Features:
    - Per-resource mutex locks
    - Lease-based ownership with TTL
    - Fencing tokens for ABA prevention
    - Deadlock prevention through sorted acquisition
    - Introspection via snapshot()
    
    Thread-safe for multi-threaded MCP server environments.
    """
    
    def __init__(self):
        self._locks: Dict[str, LockState] = {}
        self._global_lock = threading.Lock()  # Protects _locks dict
        self._next_token = 1  # Global monotonic counter
        self._telemetry = get_telemetry_sink()
    
    def _get_or_create_lock(self, resource_key: str) -> LockState:
        """Get existing lock state or create new one (caller must hold global lock)."""
        if resource_key not in self._locks:
            self._locks[resource_key] = LockState(resource_key=resource_key)
        return self._locks[resource_key]
    
    def _next_fencing_token(self) -> int:
        """Get next monotonic fencing token."""
        token = self._next_token
        self._next_token += 1
        return token
    
    def acquire(
        self,
        resource_key: str,
        agent_id: str,
        session_id: str,
        lease_ttl_sec: int,
        max_wait_ms: int,
        mode: str = "interactive",
    ) -> LockHandle:
        """
        Acquire lock on resource.
        
        Args:
            resource_key: Unique resource identifier (e.g., "code:/path/to/file.py")
            agent_id: ID of requesting agent
            session_id: ID of requesting session
            lease_ttl_sec: Lease duration in seconds
            max_wait_ms: Maximum time to wait for lock (milliseconds)
            mode: "interactive" or "batch"
        
        Returns:
            LockHandle on success
        
        Raises:
            ResourceBusyError if lock cannot be acquired within max_wait_ms
        """
        start_time = time.time()
        max_wait_sec = max_wait_ms / 1000.0
        
        # Get or create lock state
        with self._global_lock:
            lock_state = self._get_or_create_lock(resource_key)
        
        # Try to acquire the resource mutex
        deadline = start_time + max_wait_sec
        acquired = False
        
        while time.time() < deadline:
            now = time.time()
            
            # Try non-blocking acquire
            if lock_state.mutex.acquire(blocking=False):
                # We have the mutex - check if lease is valid
                if lock_state.holder_agent_id is None or lock_state.is_expired(now):
                    # Lock is available or expired - claim it
                    acquired = True
                    break
                else:
                    # Still held by someone else with valid lease
                    lock_state.mutex.release()
            
            # Sleep briefly before retry
            time.sleep(0.01)  # 10ms polling interval
        
        if not acquired:
            # Final attempt
            now = time.time()
            if lock_state.mutex.acquire(blocking=False):
                if lock_state.holder_agent_id is None or lock_state.is_expired(now):
                    acquired = True
                else:
                    lock_state.mutex.release()
        
        if not acquired:
            # Timeout - log and raise
            wait_ms = (time.time() - start_time) * 1000
            self._telemetry.log_lock_timeout(
                resource_key=resource_key,
                agent_id=agent_id,
                session_id=session_id,
                max_wait_ms=max_wait_ms,
                holder_agent_id=lock_state.holder_agent_id,
                holder_session_id=lock_state.holder_session_id,
            )
            raise ResourceBusyError(
                resource_key=resource_key,
                holder_agent_id=lock_state.holder_agent_id,
                holder_session_id=lock_state.holder_session_id,
                wait_ms=wait_ms,
                max_wait_ms=max_wait_ms,
            )
        
        # Lock acquired - update state
        now = time.time()
        fencing_token = self._next_fencing_token()
        lease_expiry = now + lease_ttl_sec
        
        lock_state.holder_agent_id = agent_id
        lock_state.holder_session_id = session_id
        lock_state.fencing_token = fencing_token
        lock_state.acquired_at = now
        lock_state.lease_expiry_ts = lease_expiry
        
        wait_ms = (now - start_time) * 1000
        
        # Log acquisition
        self._telemetry.log_lock_acquired(
            resource_key=resource_key,
            agent_id=agent_id,
            session_id=session_id,
            fencing_token=fencing_token,
            lease_ttl_sec=lease_ttl_sec,
            wait_ms=wait_ms,
        )
        
        return LockHandle(
            resource_key=resource_key,
            agent_id=agent_id,
            session_id=session_id,
            fencing_token=fencing_token,
            acquired_at=now,
            lease_expiry_ts=lease_expiry,
        )
    
    def release(
        self,
        resource_key: str,
        agent_id: str,
        session_id: str,
        fencing_token: int,
    ):
        """
        Release lock on resource.
        
        Args:
            resource_key: Resource to release
            agent_id: Agent releasing lock
            session_id: Session releasing lock
            fencing_token: Token from LockHandle
        
        Raises:
            ValueError if lock not held by this agent/session or token mismatch
        """
        with self._global_lock:
            if resource_key not in self._locks:
                raise ValueError(f"Lock not found for resource: {resource_key}")
            
            lock_state = self._locks[resource_key]
        
        # Verify ownership and token
        if not lock_state.is_held_by(agent_id, session_id):
            raise ValueError(
                f"Lock not held by agent={agent_id} session={session_id} "
                f"(held by agent={lock_state.holder_agent_id} "
                f"session={lock_state.holder_session_id})"
            )
        
        if lock_state.fencing_token != fencing_token:
            raise ValueError(
                f"Fencing token mismatch: expected={lock_state.fencing_token} "
                f"got={fencing_token}"
            )
        
        # Calculate hold duration
        now = time.time()
        held_duration_ms = (now - lock_state.acquired_at) * 1000
        
        # Clear holder info
        lock_state.holder_agent_id = None
        lock_state.holder_session_id = None
        lock_state.lease_expiry_ts = 0.0
        lock_state.acquired_at = 0.0
        
        # Release mutex
        lock_state.mutex.release()
        
        # Log release
        self._telemetry.log_lock_released(
            resource_key=resource_key,
            agent_id=agent_id,
            session_id=session_id,
            fencing_token=fencing_token,
            held_duration_ms=held_duration_ms,
        )
    
    def renew(
        self,
        resource_key: str,
        agent_id: str,
        session_id: str,
        fencing_token: int,
        lease_ttl_sec: int,
    ):
        """
        Renew lease on held lock.
        
        Args:
            resource_key: Resource to renew
            agent_id: Agent renewing lock
            session_id: Session renewing lock
            fencing_token: Current fencing token
            lease_ttl_sec: New lease duration
        
        Raises:
            ValueError if lock not held or token mismatch
        """
        with self._global_lock:
            if resource_key not in self._locks:
                raise ValueError(f"Lock not found for resource: {resource_key}")
            
            lock_state = self._locks[resource_key]
        
        # Verify ownership and token
        if not lock_state.is_held_by(agent_id, session_id):
            raise ValueError("Lock not held by this agent/session")
        
        if lock_state.fencing_token != fencing_token:
            raise ValueError("Fencing token mismatch")
        
        # Renew lease
        now = time.time()
        lock_state.lease_expiry_ts = now + lease_ttl_sec
        
        logger.debug(
            f"Renewed lease for {resource_key} by {agent_id}/{session_id}, "
            f"new expiry: {lock_state.lease_expiry_ts}"
        )
    
    def snapshot(self) -> List[Dict]:
        """
        Get snapshot of all active locks for introspection.
        
        Returns:
            List of lock state dictionaries
        """
        now = time.time()
        snapshot = []
        
        with self._global_lock:
            for resource_key, lock_state in self._locks.items():
                if lock_state.holder_agent_id is not None:
                    held_duration_ms = (now - lock_state.acquired_at) * 1000
                    ttl_remaining_sec = max(0, lock_state.lease_expiry_ts - now)
                    
                    snapshot.append({
                        "resource_key": resource_key,
                        "holder_agent_id": lock_state.holder_agent_id,
                        "holder_session_id": lock_state.holder_session_id,
                        "fencing_token": lock_state.fencing_token,
                        "held_duration_ms": round(held_duration_ms, 2),
                        "ttl_remaining_sec": round(ttl_remaining_sec, 2),
                        "is_expired": lock_state.is_expired(now),
                    })
        
        return snapshot


class ResourceBusyError(Exception):
    """Raised when lock acquisition times out due to contention."""
    
    def __init__(
        self,
        resource_key: str,
        holder_agent_id: Optional[str],
        holder_session_id: Optional[str],
        wait_ms: float,
        max_wait_ms: int,
    ):
        self.resource_key = resource_key
        self.holder_agent_id = holder_agent_id
        self.holder_session_id = holder_session_id
        self.wait_ms = wait_ms
        self.max_wait_ms = max_wait_ms
        
        msg = (
            f"Resource busy: {resource_key} "
            f"(waited {wait_ms:.0f}ms, max {max_wait_ms}ms)"
        )
        if holder_agent_id:
            msg += f" - held by {holder_agent_id}/{holder_session_id}"
        
        super().__init__(msg)
    
    def to_dict(self):
        """Convert to MCP error payload."""
        return {
            "resource_key": self.resource_key,
            "holder_agent_id": self.holder_agent_id,
            "holder_session_id": self.holder_session_id,
            "wait_ms": round(self.wait_ms, 2),
            "max_wait_ms": self.max_wait_ms,
        }


# Global singleton instance
_lock_manager: Optional[LockManager] = None


def get_lock_manager() -> LockManager:
    """Get or create global lock manager."""
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = LockManager()
    return _lock_manager
