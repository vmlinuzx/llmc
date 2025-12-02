from __future__ import annotations

from pathlib import Path

from tools.rag.config import (
    DEFAULT_EST_TOKENS_PER_SPAN,
    get_est_tokens_per_span,
)


def _write_toml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_get_est_tokens_per_span_uses_config_value(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path
    llmc = repo_root / "llmc.toml"
    monkeypatch.delenv("LLMC_EST_TOKENS_PER_SPAN", raising=False)
    _write_toml(
        llmc,
        """
[enrichment]
est_tokens_per_span = 123
""",
    )

    assert get_est_tokens_per_span(repo_root) == 123


def test_get_est_tokens_per_span_env_overrides_config(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path
    llmc = repo_root / "llmc.toml"
    _write_toml(
        llmc,
        """
[enrichment]
est_tokens_per_span = 123
""",
    )
    monkeypatch.setenv("LLMC_EST_TOKENS_PER_SPAN", "456")

    assert get_est_tokens_per_span(repo_root) == 456


def test_get_est_tokens_per_span_defaults_when_missing(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path
    monkeypatch.delenv("LLMC_EST_TOKENS_PER_SPAN", raising=False)

    assert get_est_tokens_per_span(repo_root) == DEFAULT_EST_TOKENS_PER_SPAN
