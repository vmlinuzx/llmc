from __future__ import annotations

from typing import Any

import pytest

from tools.rag.enrichment_backends import BackendCascade, BackendError


class _FakeBackend:
    """Simple fake backend for testing BackendCascade."""

    def __init__(self, name: str, should_fail: bool = False, failure_type: str = "runtime") -> None:
        self._name = name
        self._should_fail = should_fail
        self._failure_type = failure_type
        # Minimal config shim
        self.config = type("Cfg", (), {"name": name, "provider": "fake", "model": None})()

    def describe_host(self) -> str | None:
        return self._name

    def generate(
        self, prompt: str, *, item: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if self._should_fail:
            raise BackendError(f"{self._name} failed", failure_type=self._failure_type)
        return {"ok": self._name}, {"model": self._name}


def test_cascade_single_success() -> None:
    backend = _FakeBackend("b1", should_fail=False)
    cascade = BackendCascade([backend])
    result, meta, attempts = cascade.generate_for_span("prompt", item={})
    assert result["ok"] == "b1"
    assert meta["model"] == "b1"
    assert len(attempts) == 1
    assert attempts[0].backend_name == "b1"
    assert attempts[0].success is True


def test_cascade_all_fail() -> None:
    b1 = _FakeBackend("b1", should_fail=True, failure_type="runtime")
    b2 = _FakeBackend("b2", should_fail=True, failure_type="validation")
    cascade = BackendCascade([b1, b2])
    with pytest.raises(BackendError) as excinfo:
        cascade.generate_for_span("prompt", item={})
    err = excinfo.value
    # Last failure type wins
    assert err.failure_type == "validation"
    assert err.attempts is not None
    assert len(err.attempts) == 2
    assert err.attempts[0].backend_name == "b1"
    assert err.attempts[1].backend_name == "b2"
    assert err.attempts[0].success is False
    assert err.attempts[1].success is False
