from __future__ import annotations

from pathlib import Path
from typing import Mapping

from tools.rag.config_enrichment import (
    EnrichmentBackendSpec,
    EnrichmentConfig,
    EnrichmentConfigError,
    load_enrichment_config,
    select_chain,
    filter_chain_for_tier,
)


def _write_toml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_load_enrichment_config_default_when_missing(tmp_path: Path) -> None:
    repo_root = tmp_path
    env: Mapping[str, str] = {}
    config = load_enrichment_config(repo_root, env=env)
    assert isinstance(config, EnrichmentConfig)
    assert config.default_chain == "default"
    assert "default" in config.chains
    assert config.chains["default"]
    spec = config.chains["default"][0]
    assert spec.provider == "ollama"
    assert spec.routing_tier == "7b"


def test_load_enrichment_config_from_toml(tmp_path: Path) -> None:
    repo_root = tmp_path
    llmc = repo_root / "llmc.toml"
    _write_toml(
        llmc,
        """
[enrichment]
default_chain = "main"
concurrency = 3
cooldown_seconds = 120

[[enrichment.chain]]
chain = "main"
name = "athena-7b"
provider = "ollama"
model = "qwen2.5:7b-instruct-q4_K_M"
url = "http://athena:11434"
routing_tier = "7b"
timeout_seconds = 45
enabled = true

[enrichment.chain.options]
num_ctx = 8192
""",
    )
    env: Mapping[str, str] = {}
    config = load_enrichment_config(repo_root, env=env)
    assert config.default_chain == "main"
    assert config.concurrency == 3
    assert config.cooldown_seconds == 120
    assert "main" in config.chains
    specs = config.chains["main"]
    assert len(specs) == 1
    spec = specs[0]
    assert spec.name == "athena-7b"
    assert spec.provider == "ollama"
    assert spec.model == "qwen2.5:7b-instruct-q4_K_M"
    assert spec.url == "http://athena:11434"
    assert spec.routing_tier == "7b"


def test_env_overrides_concurrency_and_cooldown(tmp_path: Path) -> None:
    repo_root = tmp_path
    llmc = repo_root / "llmc.toml"
    _write_toml(
        llmc,
        """
[enrichment]
default_chain = "default"
concurrency = 1
cooldown_seconds = 0
""",
    )
    env = {
        "ENRICH_CONCURRENCY": "5",
        "ENRICH_COOLDOWN_SECONDS": "10",
    }
    config = load_enrichment_config(repo_root, env=env)
    assert config.concurrency == 5
    assert config.cooldown_seconds == 10


def test_select_chain_filters_disabled_entries() -> None:
    spec1 = EnrichmentBackendSpec(
        name="s1",
        chain="default",
        provider="ollama",
        model=None,
        url=None,
        routing_tier="7b",
        timeout_seconds=None,
        options={},
        enabled=False,
    )
    spec2 = EnrichmentBackendSpec(
        name="s2",
        chain="default",
        provider="gateway",
        model="gemini-2.5-flash",
        url=None,
        routing_tier="14b",
        timeout_seconds=None,
        options={},
        enabled=True,
    )
    config = EnrichmentConfig(
        default_chain="default",
        concurrency=1,
        cooldown_seconds=0,
        batch_size=5,
        max_retries_per_span=3,
        chains={"default": [spec1, spec2]},
    )
    selected = select_chain(config, None)
    assert [s.name for s in selected] == ["s2"]


def test_filter_chain_for_tier_respects_routing_tier() -> None:
    chain = [
        EnrichmentBackendSpec(
            name="s1",
            chain="default",
            provider="ollama",
            model=None,
            url=None,
            routing_tier=None,
            timeout_seconds=None,
            options={},
            enabled=True,
        ),
        EnrichmentBackendSpec(
            name="s2",
            chain="default",
            provider="ollama",
            model=None,
            url=None,
            routing_tier="7b",
            timeout_seconds=None,
            options={},
            enabled=True,
        ),
        EnrichmentBackendSpec(
            name="s3",
            chain="default",
            provider="gateway",
            model=None,
            url=None,
            routing_tier="14b",
            timeout_seconds=None,
            options={},
            enabled=True,
        ),
    ]

    tier_7b = filter_chain_for_tier(chain, "7b")
    assert [s.name for s in tier_7b] == ["s1", "s2"]

    tier_14b = filter_chain_for_tier(chain, "14b")
    assert [s.name for s in tier_14b] == ["s3"]
