"""Backend abstraction and cascade helpers for enrichment."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Dict, List, Optional, Protocol, Tuple


@dataclass
class AttemptRecord:
    """Summary of a single backend attempt."""

    backend_name: str
    provider: str
    model: Optional[str]
    duration_sec: float
    success: bool
    failure_type: Optional[str]
    error_message: Optional[str]
    host: Optional[str]
    gpu_stats: Optional[Dict[str, Any]]


class BackendError(Exception):
    """Error raised when a backend or cascade fails."""

    def __init__(
        self,
        message: str,
        *,
        failure_type: str | None = None,
        attempts: List[AttemptRecord] | None = None,
        failure: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_type: str | None = failure_type
        self.attempts: List[AttemptRecord] | None = attempts
        self.failure: Any | None = failure


class BackendAdapter(Protocol):
    """Protocol for concrete backends."""

    @property
    def config(self) -> Any:  # pragma: no cover - structural only
        """Return the underlying config object for this backend."""

    def generate(
        self,
        prompt: str,
        *,
        item: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:  # pragma: no cover - interface only
        """Generate an enrichment result for a single span."""

    def describe_host(self) -> str | None:  # pragma: no cover - optional
        """Return a human-friendly description of the host/endpoint."""


@dataclass
class BackendCascade:
    """Simple ordered cascade of backends."""

    backends: List[BackendAdapter]

    def generate_for_span(
        self,
        prompt: str,
        *,
        item: Dict[str, Any],
        start_index: int = 0,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[AttemptRecord]]:
        attempts: List[AttemptRecord] = []
        last_error: BackendError | None = None

        for idx in range(start_index, len(self.backends)):
            backend = self.backends[idx]
            start = time.monotonic()
            try:
                result, meta = backend.generate(prompt, item=item)
            except BackendError as exc:
                duration = time.monotonic() - start
                cfg = getattr(backend, "config", None)
                backend_name = str(getattr(cfg, "name", f"backend-{idx}"))
                provider = str(getattr(cfg, "provider", "") or "")
                model_attr = getattr(cfg, "model", None)
                model: Optional[str] = model_attr if isinstance(model_attr, str) else None
                host: Optional[str] = None
                if hasattr(backend, "describe_host"):
                    try:
                        host = backend.describe_host()
                    except Exception:  # pragma: no cover - defensive
                        host = None
                attempts.append(
                    AttemptRecord(
                        backend_name=backend_name,
                        provider=provider,
                        model=model,
                        duration_sec=duration,
                        success=False,
                        failure_type=getattr(exc, "failure_type", None),
                        error_message=str(exc),
                        host=host,
                        gpu_stats=None,
                    )
                )
                last_error = exc
                continue

            # Success path.
            duration = time.monotonic() - start
            cfg = getattr(backend, "config", None)
            backend_name = str(getattr(cfg, "name", f"backend-{idx}"))
            provider = str(getattr(cfg, "provider", "") or "")
            resolved_model: Optional[str] = None
            meta_model = meta.get("model")
            if isinstance(meta_model, str) and meta_model:
                resolved_model = meta_model
            else:
                cfg_model = getattr(cfg, "model", None)
                if isinstance(cfg_model, str) and cfg_model:
                    resolved_model = cfg_model
            resolved_host: Optional[str] = None
            if "host" in meta and isinstance(meta.get("host"), str):
                resolved_host = str(meta["host"])
            elif hasattr(backend, "describe_host"):
                try:
                    resolved_host = backend.describe_host()
                except Exception:  # pragma: no cover - defensive
                    resolved_host = None
            attempts.append(
                AttemptRecord(
                    backend_name=backend_name,
                    provider=provider,
                    model=resolved_model,
                    duration_sec=duration,
                    success=True,
                    failure_type=None,
                    error_message=None,
                    host=resolved_host,
                    gpu_stats=None,
                )
            )
            return result, meta, attempts

        # If we get here, every backend failed.
        if last_error is None:
            raise BackendError(
                "Backend cascade has no backends to execute",
                failure_type="backend_error",
                attempts=attempts,
            )

        raise BackendError(
            "All backends in cascade failed",
            failure_type=getattr(last_error, "failure_type", None),
            attempts=attempts,
            failure=getattr(last_error, "failure", None),
        ) from last_error


__all__ = [
    "BackendError",
    "BackendAdapter",
    "AttemptRecord",
    "BackendCascade",
]
