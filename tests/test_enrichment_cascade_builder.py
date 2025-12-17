from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import scripts.qwen_enrich_batch as qeb
from llmc.rag.enrichment_backends import BackendCascade


class _FakeOllamaAdapter:
    def __init__(
        self,
        *,
        config: object | None,
        repo_root: Path,
        args: SimpleNamespace,
        host_url: str,
        host_label: str | None,
        tier_preset: dict[str, Any],
        tier_for_attempt: str,
    ) -> None:
        self.config = config
        self.repo_root = repo_root
        self.args = args
        self.host_url = host_url
        self.host_label = host_label
        self.tier_preset = tier_preset
        self.tier_for_attempt = tier_for_attempt


class _FakeGatewayAdapter:
    def __init__(
        self,
        *,
        config: object | None,
        repo_root: Path,
        args: SimpleNamespace,
    ) -> None:
        self.config = config
        self.repo_root = repo_root
        self.args = args


def _make_args() -> SimpleNamespace:
    return SimpleNamespace(
        verbose=False,
        retries=1,
        retry_wait=0.1,
        gateway_path=None,
        gateway_timeout=qeb.GATEWAY_DEFAULT_TIMEOUT,
    )


def test_build_cascade_for_ollama_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simplify PRESET_CACHE for deterministic behaviour.
    monkeypatch.setattr(
        qeb,
        "PRESET_CACHE",
        {
            "7b": {"model": "m7", "options": {"num_ctx": 4096}, "keep_alive": "30m"},
            "14b": {"model": "m14"},
        },
    )

    monkeypatch.setattr(qeb, "_OllamaBackendAdapter", _FakeOllamaAdapter)
    monkeypatch.setattr(qeb, "_GatewayBackendAdapter", _FakeGatewayAdapter)

    ollama_hosts = [
        {"label": "athena", "url": "http://athena:11434"},
        {"label": "backup", "url": "http://backup:11434"},
    ]

    cascade, preset_key, tier_preset, host_label, host_url, selected_backend, chain_name = (
        qeb._build_cascade_for_attempt(
            backend="auto",
            tier_for_attempt="7b",
            repo_root=Path("."),
            args=_make_args(),
            ollama_host_chain=ollama_hosts,
            current_host_idx=0,
            host_chain_count=len(ollama_hosts),
        )
    )

    assert isinstance(cascade, BackendCascade)
    assert len(cascade.backends) == 1
    fake = cascade.backends[0]
    assert isinstance(fake, _FakeOllamaAdapter)

    assert preset_key == "7b"
    assert tier_preset["model"] == "m7"
    assert host_label == "athena"
    assert host_url == "http://athena:11434"
    assert fake.host_label == host_label
    assert fake.host_url == host_url or "http://localhost:11434"
    assert selected_backend == "ollama"


def test_build_cascade_for_gateway_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        qeb,
        "PRESET_CACHE",
        {
            "7b": {"model": "m7"},
            "14b": {"model": "m14"},
        },
    )
    monkeypatch.setattr(qeb, "_OllamaBackendAdapter", _FakeOllamaAdapter)
    monkeypatch.setattr(qeb, "_GatewayBackendAdapter", _FakeGatewayAdapter)

    cascade, preset_key, tier_preset, host_label, host_url, selected_backend, chain_name = (
        qeb._build_cascade_for_attempt(
            backend="gateway",
            tier_for_attempt="nano",
            repo_root=Path("."),
            args=_make_args(),
            ollama_host_chain=[],
            current_host_idx=0,
            host_chain_count=1,
        )
    )

    assert isinstance(cascade, BackendCascade)
    assert len(cascade.backends) == 1
    fake = cascade.backends[0]
    assert isinstance(fake, _FakeGatewayAdapter)

    assert preset_key == "7b"
    assert tier_preset["model"] == "m7"
    assert host_label is None
    assert host_url is None
    assert selected_backend in {"gateway", "nano"}


def test_build_cascade_for_unknown_backend_falls_back_to_ollama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        qeb,
        "PRESET_CACHE",
        {
            "7b": {"model": "m7"},
            "14b": {"model": "m14"},
        },
    )
    monkeypatch.setattr(qeb, "_OllamaBackendAdapter", _FakeOllamaAdapter)
    monkeypatch.setattr(qeb, "_GatewayBackendAdapter", _FakeGatewayAdapter)

    cascade, preset_key, tier_preset, host_label, host_url, selected_backend, chain_name = (
        qeb._build_cascade_for_attempt(
            backend="weird",
            tier_for_attempt="7b",
            repo_root=Path("."),
            args=_make_args(),
            ollama_host_chain=[],
            current_host_idx=0,
            host_chain_count=1,
        )
    )

    assert isinstance(cascade, BackendCascade)
    assert len(cascade.backends) == 1
    fake = cascade.backends[0]
    assert isinstance(fake, _FakeOllamaAdapter)

    assert preset_key == "7b"
    assert tier_preset["model"] == "m7"
    assert selected_backend == "ollama"
