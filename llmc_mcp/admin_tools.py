"""
MAASL Introspection Tools - Phase 7

MCP admin tools for debugging and monitoring MAASL coordination layer.

Tools:
- llmc.locks: List active locks
- llmc.stomp_stats: Contention metrics
- llmc.docgen_status: Recent docgen operations
"""

import time
from dataclasses import asdict
from typing import Dict, List, Optional

from .docgen_guard import DocgenCoordinator
from .locks import get_lock_manager
from .telemetry import get_telemetry_sink


def maasl_locks() -> Dict:
    """
    List all currently active MAASL locks.
    
    Returns:
        Dict with:
        - count: Number of active locks
        - locks: List of lock states with:
            - resource_key: Resource being locked
            - holder_agent_id: Agent holding the lock
            - holder_session_id: Session ID
            - fencing_token: Monotonic lock version
            - held_duration_ms: How long lock has been held
            - ttl_remaining_sec: Time until lease expires
            - is_expired: Whether lease has expired
    
    Example:
        >>> result = maasl_locks()
        >>> print(f"{result['count']} active locks")
        >>> for lock in result['locks']:
        ...     print(f"{lock['resource_key']} held by {lock['holder_agent_id']}")
    """
    lock_manager = get_lock_manager()
    snapshot = lock_manager.snapshot()
    
    return {
        "count": len(snapshot),
        "locks": snapshot,
        "timestamp": time.time(),
    }


def maasl_stomp_stats() -> Dict:
    """
    Get aggregated MAASL contention and coordination statistics.
    
    Returns:
        Dict with:
        - lock_acquisitions: Total successful lock acquisitions
        - lock_timeouts: Total lock acquisition timeouts (contention)
        - lock_releases: Total lock releases
        - db_writes: Database write statistics
        - graph_merges: Graph merge statistics
        - docgen_operations: Docgen operation statistics
        - uptime_seconds: MAASL telemetry uptime
    
    Example:
        >>> stats = maasl_stomp_stats()
        >>> print(f"Contention rate: {stats['lock_timeouts'] / stats['lock_acquisitions']:.2%}")
    """
    telemetry = get_telemetry_sink()
    
    # Check if telemetry has stats (added in this phase)
    if not hasattr(telemetry, '_stats'):
        return {
            "error": "Stats collection not enabled",
            "message": "TelemetrySink stats tracking not initialized",
            "lock_acquisitions": 0,
            "lock_timeouts": 0,
            "lock_releases": 0,
            "db_writes": {"success": 0, "failed": 0},
            "graph_merges": 0,
            "docgen_operations": {"generated": 0, "noop": 0, "error": 0},
            "uptime_seconds": telemetry._get_uptime(),
        }
    
    stats = telemetry._stats
    
    return {
        "lock_acquisitions": stats.get("lock_acquired", 0),
        "lock_timeouts": stats.get("lock_timeout", 0),
        "lock_releases": stats.get("lock_released", 0),
        "db_writes": {
            "success": stats.get("db_write_success", 0),
            "failed": stats.get("db_write_failed", 0),
        },
        "graph_merges": stats.get("graph_merge", 0),
        "docgen_operations": {
            "generated": stats.get("docgen_generated", 0),
            "noop": stats.get("docgen_noop", 0),
            "error": stats.get("docgen_error", 0),
        },
        "stomp_guard_calls": {
            "success": stats.get("stomp_guard_success", 0),
            "failed": stats.get("stomp_guard_failed", 0),
        },
        "uptime_seconds": telemetry._get_uptime(),
    }


def maasl_docgen_status(
    coordinator: Optional[DocgenCoordinator] = None,
    limit: int = 10
) -> Dict:
    """
    Get recent documentation generation operations.
    
    Args:
        coordinator: DocgenCoordinator instance (optional, for external callers)
        limit: Maximum number of recent operations to return
    
    Returns:
        Dict with:
        - count: Number of operations returned
        - operations: List of DocgenResult objects as dicts
        - buffer_size: Maximum buffer size
    
    Note:
        If coordinator is None, this returns a stub response.
        In production MCP context, the coordinator should be injected.
    
    Example:
        >>> status = maasl_docgen_status(coordinator, limit=5)
        >>> for op in status['operations']:
        ...     print(f"{op['status']}: {op['source_file']} ({op['duration_ms']}ms)")
    """
    if coordinator is None:
        return {
            "error": "No DocgenCoordinator available",
            "message": "DocgenCoordinator must be passed to this function",
            "count": 0,
            "operations": [],
        }
    
    operations = coordinator.get_status(limit=limit)
    
    return {
        "count": len(operations),
        "operations": [asdict(op) for op in operations],
        "buffer_size": coordinator.BUFFER_SIZE,
        "timestamp": operations[0].timestamp if operations else None,
    }


# Convenience aliases for MCP tool registration
get_maasl_locks = maasl_locks
get_stomp_stats = maasl_stomp_stats
get_docgen_status = maasl_docgen_status
