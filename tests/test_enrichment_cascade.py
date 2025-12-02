from __future__ import annotations

from typing import Any

import pytest

from tools.rag.config_enrichment import BackendConfig
from tools.rag.enrichment_backends import BackendCascade, BackendError


class _FakeBackend:
    def __init__(self, config: BackendConfig, *, should_fail: bool = False, label: str = "") -> None:
        self.config = config
        self._should_fail = should_fail
        self._label = label or config.name
        self.calls: list[str] = []

    def generate(self, prompt: str, *, item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        self.calls.append(prompt)
        if self._should_fail:
            raise BackendError(f"{self._label} failed")
        return f"{self._label}: {prompt}", {"model": self.config.model or "dummy", "host": "test-host"}


def test_cascade_tries_second_on_backend_error() -> None:
    first = _FakeBackend(BackendConfig(name="first", provider="ollama"), should_fail=True)
    second = _FakeBackend(BackendConfig(name="second", provider="ollama"), should_fail=False)
    cascade = BackendCascade([first, second])

    text, meta, attempts = cascade.generate_for_span("hello", item={"span_hash": "abc"})

    assert text.startswith("second:")
    assert meta["model"] == second.config.model or "dummy"
    assert len(attempts) == 2
    assert attempts[0].success is False
    assert attempts[1].success is True
    assert first.calls == ["hello"]
    assert second.calls == ["hello"]


def test_cascade_raises_after_all_fail() -> None:
    first = _FakeBackend(BackendConfig(name="first", provider="ollama"), should_fail=True)
    second = _FakeBackend(BackendConfig(name="second", provider="gateway"), should_fail=True)
    cascade = BackendCascade([first, second])

    with pytest.raises(BackendError):
        cascade.generate_for_span("boom", item={"span_hash": "abc"})


def test_attempt_records_populated() -> None:
    backend = _FakeBackend(BackendConfig(name="only", provider="ollama", model="qwen2.5:7b"))
    cascade = BackendCascade([backend])

    text, meta, attempts = cascade.generate_for_span("hi", item={"span_hash": "abc"})

    assert text.startswith("only:")
    assert meta["model"] == "qwen2.5:7b"
    assert len(attempts) == 1
    rec = attempts[0]
    assert rec.backend_name == "only"
    assert rec.provider == "ollama"
    assert rec.model == "qwen2.5:7b"
    assert rec.success is True
    assert rec.duration_sec >= 0.0
