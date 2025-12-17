from datetime import UTC, datetime
import json
from pathlib import Path
import threading
from typing import Any

from llmc.ruta.types import TraceEvent


class TraceRecorder:
    """
    Records trace events to a JSONL file.
    Thread-safe.
    """

    def __init__(self, run_id: str, artifact_dir: Path):
        self.run_id = run_id
        self.artifact_dir = artifact_dir
        self._file_handle = None
        self._lock = threading.Lock()

        self.artifact_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        # Sanitize run_id for filename to avoid directory traversal issues
        safe_run_id = run_id.replace("/", "_").replace("\\", "_")
        self.trace_file = self.artifact_dir / f"trace_{safe_run_id}_{timestamp}.jsonl"

        self._file_handle = open(self.trace_file, "a", encoding="utf-8")
        self._step_counter = 0

    def log_event(
        self,
        event_type: str,
        agent: str,
        tool_name: str | None = None,
        args: dict[str, Any] | None = None,
        result_summary: dict[str, Any] | None = None,
        latency_ms: float | None = None,
        success: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceEvent:
        """
        Log an event to the trace.
        Returns the created event object.
        """
        with self._lock:
            self._step_counter += 1
            step = self._step_counter

        event: TraceEvent = {
            "run_id": self.run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "step": step,
            "agent": agent,
            "event": event_type,  # type: ignore
            "tool_name": tool_name,
            "args": args,
            "result_summary": result_summary,
            "latency_ms": latency_ms,
            "success": success,
            "metadata": metadata,
        }

        json_line = json.dumps(event, ensure_ascii=False)

        with self._lock:
            self._file_handle.write(json_line + "\n")
            self._file_handle.flush()

        return event

    def close(self):
        if not hasattr(self, "_lock"):
            return
        with self._lock:
            if self._file_handle:
                self._file_handle.close()
                self._file_handle = None

    def __del__(self):
        self.close()
