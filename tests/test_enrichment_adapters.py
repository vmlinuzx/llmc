from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import scripts.qwen_enrich_batch as qeb
from llmc.rag.enrichment_backends import BackendError


def _make_args() -> SimpleNamespace:
    return SimpleNamespace(
        verbose=False,
        retries=1,
        retry_wait=0.1,
        gateway_path=None,
        gateway_timeout=qeb.GATEWAY_DEFAULT_TIMEOUT,
        enforce_latin1=False,
    )


def test_ollama_adapter_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    def fake_call_qwen(prompt: str, repo_root: Path, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        calls["backend"] = kwargs.get("backend")
        calls["model_override"] = kwargs.get("model_override")
        calls["ollama_base_url"] = kwargs.get("ollama_base_url")
        calls["ollama_host_label"] = kwargs.get("ollama_host_label")
        return "RAW", {"backend": "ollama", "model": "env-model"}

    def fake_parse_and_validate(
        raw: str, item: dict[str, Any], meta: dict[str, Any], **kwargs: Any
    ):
        assert raw == "RAW"
        assert meta["backend"] == "ollama"
        return {"ok": True}, None

    monkeypatch.setattr(qeb, "call_qwen", fake_call_qwen)
    monkeypatch.setattr(qeb, "parse_and_validate", fake_parse_and_validate)

    cfg = qeb._AdapterConfigShim(
        name="athena-7b",
        provider="ollama",
        model="cfg-model",
        options={"num_ctx": 8192},
        keep_alive="30m",
    )

    adapter = qeb._OllamaBackendAdapter(
        config=cfg,
        repo_root=Path("."),
        args=_make_args(),
        host_url="http://athena:11434",
        host_label="athena",
        tier_preset={"model": "preset-model", "options": {"num_ctx": 4096}, "keep_alive": None},
        tier_for_attempt="7b",
    )

    result, meta = adapter.generate("PROMPT", item={"id": 1})
    assert result["ok"] is True
    assert meta["backend"] == "ollama"
    assert meta["host"] == "athena"
    # call_qwen meta should win when provided.
    assert meta["model"] == "env-model"

    assert calls["backend"] == "ollama"
    assert calls["ollama_base_url"] == "http://athena:11434"
    assert calls["ollama_host_label"] == "athena"


def test_ollama_adapter_validation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_call_qwen(prompt: str, repo_root: Path, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        return "RAW", {}

    failure_tuple = ("validation", ValueError("oops"), {"foo": "bar"})

    def fake_parse_and_validate(
        raw: str, item: dict[str, Any], meta: dict[str, Any], **kwargs: Any
    ):
        return None, failure_tuple

    monkeypatch.setattr(qeb, "call_qwen", fake_call_qwen)
    monkeypatch.setattr(qeb, "parse_and_validate", fake_parse_and_validate)

    adapter = qeb._OllamaBackendAdapter(
        config=None,
        repo_root=Path("."),
        args=_make_args(),
        host_url="http://localhost:11434",
        host_label=None,
        tier_preset={"model": "preset-model", "options": {"num_ctx": 4096}, "keep_alive": None},
        tier_for_attempt="7b",
    )

    with pytest.raises(BackendError) as excinfo:
        adapter.generate("PROMPT", item={"id": 2})
    err = excinfo.value
    assert err.failure_type == "validation"
    assert err.failure == failure_tuple


def test_gateway_adapter_success_respects_model_and_restores_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_model = "orig-model"
    monkeypatch.setenv("GEMINI_MODEL", original_model)

    def fake_call_qwen(prompt: str, repo_root: Path, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        # During the call, the env should be overridden.
        assert os.environ.get("GEMINI_MODEL") == "gemini-2.5-flash"
        return "RAW", {}

    def fake_parse_and_validate(
        raw: str, item: dict[str, Any], meta: dict[str, Any], **kwargs: Any
    ):
        return {"ok": True}, None

    monkeypatch.setattr(qeb, "call_qwen", fake_call_qwen)
    monkeypatch.setattr(qeb, "parse_and_validate", fake_parse_and_validate)

    cfg = qeb._AdapterConfigShim(
        name="gateway-fast",
        provider="gemini",
        model="gemini-2.5-flash",
    )

    adapter = qeb._GatewayBackendAdapter(
        config=cfg,
        repo_root=Path("."),
        args=_make_args(),
    )

    result, meta = adapter.generate("PROMPT", item={"id": 3})
    assert result["ok"] is True
    assert meta["backend"] == "gateway"
    assert meta["model"] == "gemini-2.5-flash"

    # After the call, env should be restored.
    assert os.environ.get("GEMINI_MODEL") == original_model


def test_gateway_adapter_validation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    failure_tuple = ("validation", ValueError("bad"), {"bar": "baz"})

    def fake_call_qwen(prompt: str, repo_root: Path, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        return "RAW", {}

    def fake_parse_and_validate(
        raw: str, item: dict[str, Any], meta: dict[str, Any], **kwargs: Any
    ):
        return None, failure_tuple

    monkeypatch.setattr(qeb, "call_qwen", fake_call_qwen)
    monkeypatch.setattr(qeb, "parse_and_validate", fake_parse_and_validate)

    adapter = qeb._GatewayBackendAdapter(
        config=None,
        repo_root=Path("."),
        args=_make_args(),
    )

    with pytest.raises(BackendError) as excinfo:
        adapter.generate("PROMPT", item={"id": 4})
    err = excinfo.value
    assert err.failure_type == "validation"
    assert err.failure == failure_tuple
