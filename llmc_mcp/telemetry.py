#!/usr/bin/env python3
"""
MAASL Telemetry - Structured logging and metrics for Multi-Agent Anti-Stomp Layer.

Provides lightweight structured logging for lock events, contention, and coordination metrics.
"""

import logging
import time
from typing import Any, Optional

logger = logging.getLogger("llmc-mcp.maasl")


class TelemetrySink:
    """
    Lightweight telemetry sink for MAASL events.
    
    Emits structured logs for lock acquisition, contention, and coordination events.
    Future: Can be extended to emit to MetricsCollector for aggregation.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._start_time = time.time()

    def log_lock_acquired(
        self,
        resource_key: str,
        agent_id: str,
        session_id: str,
        fencing_token: int,
        lease_ttl_sec: int,
        wait_ms: float,
    ):
        """Log successful lock acquisition."""
        if not self.enabled:
            return
        
        logger.info(
            "Lock acquired",
            extra={
                "event": "lock_acquired",
                "resource_key": resource_key,
                "agent_id": agent_id,
                "session_id": session_id,
                "fencing_token": fencing_token,
                "lease_ttl_sec": lease_ttl_sec,
                "wait_ms": round(wait_ms, 2),
            },
        )

    def log_lock_timeout(
        self,
        resource_key: str,
        agent_id: str,
        session_id: str,
        max_wait_ms: int,
        holder_agent_id: Optional[str] = None,
        holder_session_id: Optional[str] = None,
    ):
        """Log lock acquisition timeout (contention)."""
        if not self.enabled:
            return
        
        logger.warning(
            "Lock timeout",
            extra={
                "event": "lock_timeout",
                "resource_key": resource_key,
                "agent_id": agent_id,
                "session_id": session_id,
                "max_wait_ms": max_wait_ms,
                "holder_agent_id": holder_agent_id,
                "holder_session_id": holder_session_id,
            },
        )

    def log_lock_released(
        self,
        resource_key: str,
        agent_id: str,
        session_id: str,
        fencing_token: int,
        held_duration_ms: float,
    ):
        """Log lock release."""
        if not self.enabled:
            return
        
        logger.info(
            "Lock released",
            extra={
                "event": "lock_released",
                "resource_key": resource_key,
                "agent_id": agent_id,
                "session_id": session_id,
                "fencing_token": fencing_token,
                "held_duration_ms": round(held_duration_ms, 2),
            },
        )

    def log_db_write(
        self,
        agent_id: str,
        session_id: str,
        intent: str,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None,
    ):
        """Log database write operation."""
        if not self.enabled:
            return
        
        level = logging.INFO if success else logging.ERROR
        logger.log(
            level,
            f"DB write {'succeeded' if success else 'failed'}",
            extra={
                "event": "db_write",
                "agent_id": agent_id,
                "session_id": session_id,
                "intent": intent,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "error": error,
            },
        )

    def log_graph_merge(
        self,
        agent_id: str,
        session_id: str,
        nodes_added: int,
        edges_added: int,
        conflicts: int,
        duration_ms: float,
    ):
        """Log knowledge graph merge operation."""
        if not self.enabled:
            return
        
        logger.info(
            "Graph merge completed",
            extra={
                "event": "graph_merge",
                "agent_id": agent_id,
                "session_id": session_id,
                "nodes_added": nodes_added,
                "edges_added": edges_added,
                "conflicts": conflicts,
                "duration_ms": round(duration_ms, 2),
            },
        )

    def log_docgen(
        self,
        file: str,
        status: str,
        hash_match: bool,
        duration_ms: float,
        agent_id: str,
        session_id: str,
        error: Optional[str] = None,
    ):
        """Log documentation generation event."""
        if not self.enabled:
            return
        
        level = logging.INFO if not error else logging.ERROR
        logger.log(
            level,
            f"Docgen {status}",
            extra={
                "event": "docgen",
                "file": file,
                "status": status,
                "hash_match": hash_match,
                "duration_ms": round(duration_ms, 2),
                "agent_id": agent_id,
                "session_id": session_id,
                "error": error,
            },
        )

    def log_stomp_guard_call(
        self,
        intent: str,
        mode: str,
        agent_id: str,
        session_id: str,
        resource_count: int,
        duration_ms: float,
        success: bool,
        error_type: Optional[str] = None,
    ):
        """Log high-level call_with_stomp_guard invocation."""
        if not self.enabled:
            return
        
        level = logging.INFO if success else logging.WARNING
        logger.log(
            level,
            f"Stomp guard: {intent} {'succeeded' if success else 'failed'}",
            extra={
                "event": "stomp_guard_call",
                "intent": intent,
                "mode": mode,
                "agent_id": agent_id,
                "session_id": session_id,
                "resource_count": resource_count,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "error_type": error_type,
            },
        )


# Global singleton instance
_telemetry_sink: Optional[TelemetrySink] = None


def get_telemetry_sink() -> TelemetrySink:
    """Get or create global telemetry sink."""
    global _telemetry_sink
    if _telemetry_sink is None:
        _telemetry_sink = TelemetrySink()
    return _telemetry_sink


def configure_telemetry(enabled: bool = True):
    """Configure global telemetry sink."""
    global _telemetry_sink
    _telemetry_sink = TelemetrySink(enabled=enabled)
