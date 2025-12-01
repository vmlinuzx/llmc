"""Observability module for LLMC MCP Server (M4).

Provides:
- Correlation ID generation
- JSON structured logging
- In-memory metrics collection
- CSV token audit trail
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from llmc_mcp.audit import TokenAuditWriter
from llmc_mcp.config import McpObservabilityConfig


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing."""
    return str(uuid.uuid4())[:8]  # Short form for readability


class JsonLogFormatter(logging.Formatter):
    """JSON structured log formatter with correlation ID support."""
    
    def __init__(self, include_correlation_id: bool = True):
        super().__init__()
        self.include_correlation_id = include_correlation_id
        self.session_id = os.getenv("LLMC_TE_SESSION_ID") or os.getenv("TE_SESSION_ID")
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        
        # Add session_id if present
        if self.session_id:
            log_data["session_id"] = self.session_id
        
        # Add correlation_id if present on record
        if self.include_correlation_id and hasattr(record, "correlation_id"):
            log_data["cid"] = record.correlation_id
        
        # Add extra fields if present
        if hasattr(record, "tool"):
            log_data["tool"] = record.tool
        if hasattr(record, "latency_ms"):
            log_data["latency_ms"] = record.latency_ms
        if hasattr(record, "status"):
            log_data["status"] = record.status
        if hasattr(record, "error"):
            log_data["error"] = record.error
        
        # Add exception info if present
        if record.exc_info:
            log_data["exc"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, separators=(",", ":"))



@dataclass
class ToolMetrics:
    """Metrics for a single tool."""
    call_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0
    
    @property
    def avg_latency_ms(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.total_latency_ms / self.call_count


class MetricsCollector:
    """In-memory metrics collector for MCP server.
    
    Thread-safe collection of:
    - Per-tool call counts, errors, latencies
    - Global request counts
    - Token in/out estimates (when audit enabled)
    """
    
    def __init__(self):
        self._lock = Lock()
        self._tools: dict[str, ToolMetrics] = defaultdict(ToolMetrics)
        self._total_requests: int = 0
        self._total_errors: int = 0
        self._start_time: float = time.time()
        self._tokens_in: int = 0
        self._tokens_out: int = 0
    
    def record_call(
        self,
        tool: str,
        latency_ms: float,
        success: bool,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        """Record a tool call with metrics."""
        with self._lock:
            self._total_requests += 1
            if not success:
                self._total_errors += 1
            
            metrics = self._tools[tool]
            metrics.call_count += 1
            if not success:
                metrics.error_count += 1
            metrics.total_latency_ms += latency_ms
            metrics.min_latency_ms = min(metrics.min_latency_ms, latency_ms)
            metrics.max_latency_ms = max(metrics.max_latency_ms, latency_ms)
            
            self._tokens_in += tokens_in
            self._tokens_out += tokens_out
    
    def get_stats(self) -> dict[str, Any]:
        """Get current metrics snapshot."""
        with self._lock:
            uptime_s = time.time() - self._start_time
            tool_stats = {}
            for name, m in self._tools.items():
                tool_stats[name] = {
                    "calls": m.call_count,
                    "errors": m.error_count,
                    "avg_ms": round(m.avg_latency_ms, 2),
                    "min_ms": round(m.min_latency_ms, 2) if m.min_latency_ms != float("inf") else 0,
                    "max_ms": round(m.max_latency_ms, 2),
                }
            
            return {
                "uptime_s": round(uptime_s, 1),
                "total_requests": self._total_requests,
                "total_errors": self._total_errors,
                "error_rate": round(self._total_errors / max(1, self._total_requests), 4),
                "tokens_in": self._tokens_in,
                "tokens_out": self._tokens_out,
                "tools": tool_stats,
            }
    
    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock:
            self._tools.clear()
            self._total_requests = 0
            self._total_errors = 0
            self._start_time = time.time()
            self._tokens_in = 0
            self._tokens_out = 0


class ObservabilityContext:
    """Unified observability context for the MCP server.
    
    Manages:
    - JSON log formatting
    - Metrics collection
    - Token audit CSV
    
    Usage:
        obs = ObservabilityContext(config.observability)
        
        # In request handler:
        cid = obs.correlation_id()
        start = time.time()
        # ... do work ...
        obs.record(cid, "read_file", latency_ms=..., success=True)
    """
    
    def __init__(self, config: McpObservabilityConfig):
        self.config = config
        self.enabled = config.enabled
        
        # Metrics collector (always available, even if disabled)
        self.metrics = MetricsCollector()
        
        # Token audit writer
        self.audit = TokenAuditWriter(
            csv_path=config.csv_path,
            enabled=config.enabled and config.csv_token_audit_enabled,
        )
    
    def correlation_id(self) -> str:
        """Generate a new correlation ID."""
        return generate_correlation_id()
    
    def record(
        self,
        correlation_id: str,
        tool: str,
        latency_ms: float,
        success: bool,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        """Record a tool call to metrics and audit trail."""
        if not self.enabled:
            return
        
        self.metrics.record_call(
            tool=tool,
            latency_ms=latency_ms,
            success=success,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
        
        self.audit.record(
            correlation_id=correlation_id,
            tool=tool,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            success=success,
        )
    
    def get_stats(self) -> dict[str, Any]:
        """Get current metrics snapshot."""
        return self.metrics.get_stats()


def setup_logging(config: McpObservabilityConfig, logger_name: str = "llmc-mcp") -> logging.Logger:
    """Configure logging based on observability settings.
    
    Args:
        config: Observability configuration
        logger_name: Name of logger to configure
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(logger_name)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Set level
    level = getattr(logging, config.log_level.upper(), logging.INFO)
    logger.setLevel(level)
    
    # Create stderr handler
    handler = logging.StreamHandler()
    handler.setLevel(level)
    
    # Use JSON or text formatter
    if config.log_format == "json":
        handler.setFormatter(JsonLogFormatter(
            include_correlation_id=config.include_correlation_id
        ))
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
    
    logger.addHandler(handler)
    
    return logger
