#!/usr/bin/env python3
"""
MAASL Telemetry - Structured logging and metrics for Multi-Agent Anti-Stomp Layer.

Provides lightweight structured logging for lock events, contention, and coordination metrics.
"""

import logging
import time

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

        # Stats collection for introspection
        self._stats = {
            "lock_acquired": 0,
            "lock_timeout": 0,
            "lock_released": 0,
            "db_write_success": 0,
            "db_write_failed": 0,
            "graph_merge": 0,
            "docgen_generated": 0,
            "docgen_noop": 0,
            "docgen_error": 0,
            "stomp_guard_success": 0,
            "stomp_guard_failed": 0,
        }

    def _get_uptime(self) -> float:
        """Get telemetry uptime in seconds."""
        return time.time() - self._start_time

    def _increment_stat(self, key: str):
        """Increment a stat counter."""
        if key in self._stats:
            self._stats[key] += 1

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

        self._increment_stat("lock_acquired")
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
        holder_agent_id: str | None = None,
        holder_session_id: str | None = None,
    ):
        """Log lock acquisition timeout (contention)."""
        if not self.enabled:
            return

        self._increment_stat("lock_timeout")
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

        self._increment_stat("lock_released")
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
        error: str | None = None,
    ):
        """Log database write operation."""
        if not self.enabled:
            return

        self._increment_stat("db_write_success" if success else "db_write_failed")
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

        self._increment_stat("graph_merge")
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
        error: str | None = None,
    ):
        """Log documentation generation event."""
        if not self.enabled:
            return

        # Track by status: generated, noop, error
        if status == "generated":
            self._increment_stat("docgen_generated")
        elif status == "noop":
            self._increment_stat("docgen_noop")
        elif error:
            self._increment_stat("docgen_error")

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
        error_type: str | None = None,
    ):
        """Log high-level call_with_stomp_guard invocation."""
        if not self.enabled:
            return

        self._increment_stat("stomp_guard_success" if success else "stomp_guard_failed")
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
_telemetry_sink: TelemetrySink | None = None


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
