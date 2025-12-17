"""
Tests for enrichment_router.py – Phase 2 (SDD v2.1 sections 2.1.1-2.1.3)

Tests runtime data structures:
  - EnrichmentSliceView
  - EnrichmentRouteDecision
  - EnrichmentRouterMetricsEvent
"""

from pathlib import Path
import time

from llmc.rag.config_enrichment import EnrichmentBackendSpec, EnrichmentConfig
from llmc.rag.enrichment_router import (
    EnrichmentRouteDecision,
    EnrichmentRouterMetricsEvent,
    EnrichmentSliceView,
)


class TestEnrichmentSliceView:
    """Tests for EnrichmentSliceView (SDD 2.1.1)."""

    def test_basic_construction(self):
        """Verify basic dataclass construction with all fields."""
        view = EnrichmentSliceView(
            span_hash="sha256:abc123",
            file_path=Path("tools/rag/cli.py"),
            start_line=10,
            end_line=50,
            content_type="code",
            classifier_confidence=0.95,
            approx_token_count=500,
            importance="high",
        )
        assert view.span_hash == "sha256:abc123"
        assert view.file_path == Path("tools/rag/cli.py")
        assert view.start_line == 10
        assert view.end_line == 50
        assert view.content_type == "code"
        assert view.classifier_confidence == 0.95
        assert view.approx_token_count == 500
        assert view.importance == "high"

    def test_string_path_converted_to_path(self):
        """Verify string file_path is converted to Path in __post_init__."""
        view = EnrichmentSliceView(
            span_hash="sha256:def456",
            file_path="src/main.py",  # type: ignore[arg-type]
            start_line=1,
            end_line=100,
            content_type="code",
            classifier_confidence=0.8,
            approx_token_count=1000,
        )
        assert isinstance(view.file_path, Path)
        assert view.file_path == Path("src/main.py")

    def test_importance_defaults_to_none(self):
        """Verify importance field defaults to None."""
        view = EnrichmentSliceView(
            span_hash="sha256:ghi789",
            file_path=Path("README.md"),
            start_line=1,
            end_line=20,
            content_type="docs",
            classifier_confidence=0.99,
            approx_token_count=200,
        )
        assert view.importance is None


class TestEnrichmentRouteDecision:
    """Tests for EnrichmentRouteDecision (SDD 2.1.2)."""

    def test_basic_construction(self):
        """Verify basic dataclass construction."""
        backend = EnrichmentBackendSpec(
            name="qwen-7b",
            chain="athena_code",
            provider="ollama",
            model="qwen2.5:7b",
        )
        decision = EnrichmentRouteDecision(
            slice_type="code",
            chain_name="athena_code",
            backend_specs=[backend],
            routing_tier="7b",
            reasons=["slice_type=code maps to athena_code"],
        )
        assert decision.slice_type == "code"
        assert decision.chain_name == "athena_code"
        assert len(decision.backend_specs) == 1
        assert decision.backend_specs[0].name == "qwen-7b"
        assert decision.routing_tier == "7b"
        assert len(decision.reasons) == 1

    def test_multiple_backends_in_chain(self):
        """Verify decision can hold multiple backends (cascade)."""
        backends = [
            EnrichmentBackendSpec(name="qwen-7b", chain="cascade", provider="ollama"),
            EnrichmentBackendSpec(name="gemini-flash", chain="cascade", provider="gemini"),
        ]
        decision = EnrichmentRouteDecision(
            slice_type="docs",
            chain_name="cascade",
            backend_specs=backends,
        )
        assert len(decision.backend_specs) == 2
        assert decision.backend_specs[0].name == "qwen-7b"
        assert decision.backend_specs[1].name == "gemini-flash"

    def test_defaults(self):
        """Verify default values for optional fields."""
        decision = EnrichmentRouteDecision(
            slice_type="unknown",
            chain_name="default",
            backend_specs=[],
        )
        assert decision.routing_tier is None
        assert decision.reasons == []


class TestEnrichmentRouterMetricsEvent:
    """Tests for EnrichmentRouterMetricsEvent (SDD 2.1.3)."""

    def test_basic_construction(self):
        """Verify basic dataclass construction."""
        ts = time.time()
        event = EnrichmentRouterMetricsEvent(
            timestamp=ts,
            span_hash="sha256:xyz",
            slice_type="code",
            chain_name="athena_code",
            backend_name="qwen-7b",
            provider="ollama",
            model="qwen2.5:7b",
            routing_tier="7b",
            success=True,
            failure_type=None,
            duration_sec=1.5,
            attempt_index=0,
            total_attempts=1,
        )
        assert event.timestamp == ts
        assert event.success is True
        assert event.failure_type is None
        assert event.duration_sec == 1.5

    def test_to_json_returns_dict(self):
        """Verify to_json() returns a serializable dict."""
        event = EnrichmentRouterMetricsEvent(
            timestamp=1234567890.0,
            span_hash="sha256:test",
            slice_type="docs",
            chain_name="default",
            backend_name="gemini-flash",
            provider="gemini",
            model="gemini-2.0-flash",
            routing_tier=None,
            success=False,
            failure_type="timeout",
            duration_sec=30.0,
            attempt_index=1,
            total_attempts=2,
            reason="Backend timed out after 30s",
            extra={"retry_count": 1},
        )
        json_out = event.to_json()
        assert isinstance(json_out, dict)
        assert json_out["timestamp"] == 1234567890.0
        assert json_out["span_hash"] == "sha256:test"
        assert json_out["success"] is False
        assert json_out["failure_type"] == "timeout"
        assert json_out["reason"] == "Backend timed out after 30s"
        assert json_out["extra"] == {"retry_count": 1}

    def test_to_json_includes_all_fields(self):
        """Verify to_json() includes all 15 fields."""
        event = EnrichmentRouterMetricsEvent(
            timestamp=0.0,
            span_hash="",
            slice_type="",
            chain_name="",
            backend_name="",
            provider="",
            model=None,
            routing_tier=None,
            success=True,
            failure_type=None,
            duration_sec=0.0,
            attempt_index=0,
            total_attempts=0,
        )
        json_out = event.to_json()
        expected_keys = {
            "timestamp",
            "span_hash",
            "slice_type",
            "chain_name",
            "backend_name",
            "provider",
            "model",
            "routing_tier",
            "success",
            "failure_type",
            "duration_sec",
            "attempt_index",
            "total_attempts",
            "reason",
            "extra",
        }
        assert set(json_out.keys()) == expected_keys

    def test_failure_event(self):
        """Verify failure event can be constructed."""
        event = EnrichmentRouterMetricsEvent(
            timestamp=time.time(),
            span_hash="sha256:fail",
            slice_type="erp_product",
            chain_name="erp_chain",
            backend_name="qwen-14b",
            provider="ollama",
            model="qwen2.5:14b",
            routing_tier="14b",
            success=False,
            failure_type="abstention",
            duration_sec=5.2,
            attempt_index=0,
            total_attempts=2,
            reason="Model abstained from enrichment",
        )
        assert event.success is False
        assert event.failure_type == "abstention"


# -----------------------------------------------------------------------------
# Phase 3 Tests - EnrichmentRouter class (SDD 4.1)
# -----------------------------------------------------------------------------


class TestEnrichmentRouter:
    """Tests for EnrichmentRouter class (SDD 4.1)."""

    @staticmethod
    def _make_config(
        *,
        enable_routing: bool = False,
        routes: dict[str, str] | None = None,
        max_tier: str | None = None,
        chains: dict[str, list[EnrichmentBackendSpec]] | None = None,
    ) -> EnrichmentConfig:
        """Helper to create test configs."""
        from llmc.rag.config_enrichment import EnrichmentConfig

        default_backend = EnrichmentBackendSpec(
            name="default-backend",
            chain="default",
            provider="ollama",
        )
        code_backend = EnrichmentBackendSpec(
            name="code-backend",
            chain="code_chain",
            provider="ollama",
            routing_tier="7b",
        )
        if chains is None:
            chains = {
                "default": [default_backend],
                "code_chain": [code_backend],
            }
        return EnrichmentConfig(
            default_chain="default",
            concurrency=1,
            cooldown_seconds=0,
            batch_size=5,
            max_retries_per_span=3,
            enforce_latin1_enrichment=True,
            chains=chains,
            enable_routing=enable_routing,
            routes=routes,
            max_tier=max_tier,
            on_failure="error",
        )

    def test_router_default_chain_when_disabled(self):
        """Router uses default_chain when enable_routing=False (SDD 6.1.2)."""
        from llmc.rag.enrichment_router import EnrichmentRouter

        config = self._make_config(
            enable_routing=False,
            routes={"code": "code_chain"},
        )
        router = EnrichmentRouter(
            config=config,
            enable_routing=False,
            routes={"code": "code_chain"},
        )

        slice_view = EnrichmentSliceView(
            span_hash="sha256:test",
            file_path=Path("test.py"),
            start_line=1,
            end_line=10,
            content_type="code",
            classifier_confidence=0.9,
            approx_token_count=100,
        )
        decision = router.choose_chain(slice_view)
        assert decision.chain_name == "default"
        assert "routing disabled" in decision.reasons[0]

    def test_router_respects_chain_override(self):
        """chain_override takes precedence over routing (SDD 6.1.2)."""
        from llmc.rag.enrichment_router import EnrichmentRouter

        config = self._make_config(
            enable_routing=True,
            routes={"code": "code_chain"},
        )
        router = EnrichmentRouter(
            config=config,
            enable_routing=True,
            routes={"code": "code_chain"},
        )

        slice_view = EnrichmentSliceView(
            span_hash="sha256:test",
            file_path=Path("test.py"),
            start_line=1,
            end_line=10,
            content_type="code",
            classifier_confidence=0.9,
            approx_token_count=100,
        )
        decision = router.choose_chain(slice_view, chain_override="default")
        assert decision.chain_name == "default"
        assert "chain_override" in decision.reasons[0]

    def test_router_uses_routes_when_enabled(self):
        """Router maps slice_type -> chain when enabled (SDD 6.2.1)."""
        from llmc.rag.enrichment_router import EnrichmentRouter

        config = self._make_config(
            enable_routing=True,
            routes={"code": "code_chain", "docs": "default"},
        )
        router = EnrichmentRouter(
            config=config,
            enable_routing=True,
            routes={"code": "code_chain", "docs": "default"},
        )

        # Test code -> code_chain
        code_view = EnrichmentSliceView(
            span_hash="sha256:code",
            file_path=Path("main.py"),
            start_line=1,
            end_line=50,
            content_type="code",
            classifier_confidence=0.95,
            approx_token_count=500,
        )
        decision = router.choose_chain(code_view)
        assert decision.chain_name == "code_chain"
        assert decision.slice_type == "code"

        # Test docs -> default
        docs_view = EnrichmentSliceView(
            span_hash="sha256:docs",
            file_path=Path("README.md"),
            start_line=1,
            end_line=20,
            content_type="docs",
            classifier_confidence=0.99,
            approx_token_count=200,
        )
        decision = router.choose_chain(docs_view)
        assert decision.chain_name == "default"

    def test_router_falls_back_for_unknown_type(self):
        """Router falls back to default_chain for unknown slice_type (SDD 6.2.3)."""
        from llmc.rag.enrichment_router import EnrichmentRouter

        config = self._make_config(
            enable_routing=True,
            routes={"code": "code_chain"},
        )
        router = EnrichmentRouter(
            config=config,
            enable_routing=True,
            routes={"code": "code_chain"},
        )

        unknown_view = EnrichmentSliceView(
            span_hash="sha256:mystery",
            file_path=Path("mystery.xyz"),
            start_line=1,
            end_line=5,
            content_type="mystery_format",
            classifier_confidence=0.5,
            approx_token_count=50,
        )
        decision = router.choose_chain(unknown_view)
        assert decision.chain_name == "default"
        assert "no route for" in decision.reasons[0]


class TestNormalizeSliceType:
    """Tests for normalize_slice_type method."""

    def test_case_normalization(self):
        """Verify case insensitivity."""
        from llmc.rag.enrichment_router import EnrichmentRouter

        config = TestEnrichmentRouter._make_config()
        router = EnrichmentRouter(config=config, enable_routing=False, routes=None)

        assert router.normalize_slice_type("CODE") == "code"
        assert router.normalize_slice_type("Code") == "code"
        assert router.normalize_slice_type("DOCS") == "docs"
        assert router.normalize_slice_type("Docs") == "docs"

    def test_language_aliases(self):
        """Verify programming language aliases map to 'code'."""
        from llmc.rag.enrichment_router import EnrichmentRouter

        config = TestEnrichmentRouter._make_config()
        router = EnrichmentRouter(config=config, enable_routing=False, routes=None)

        for lang in ["python", "javascript", "typescript", "java", "rust", "go"]:
            assert router.normalize_slice_type(lang) == "code", f"{lang} should map to 'code'"

    def test_doc_aliases(self):
        """Verify documentation format aliases map to 'docs'."""
        from llmc.rag.enrichment_router import EnrichmentRouter

        config = TestEnrichmentRouter._make_config()
        router = EnrichmentRouter(config=config, enable_routing=False, routes=None)

        for fmt in ["markdown", "md", "rst", "text", "txt", "documentation"]:
            assert router.normalize_slice_type(fmt) == "docs", f"{fmt} should map to 'docs'"

    def test_empty_returns_unknown(self):
        """Verify empty/None returns 'unknown'."""
        from llmc.rag.enrichment_router import EnrichmentRouter

        config = TestEnrichmentRouter._make_config()
        router = EnrichmentRouter(config=config, enable_routing=False, routes=None)

        assert router.normalize_slice_type("") == "unknown"
        assert router.normalize_slice_type("   ") == "unknown"


# -----------------------------------------------------------------------------
# Phase 3 Tests - build_router_from_toml and env overrides (SDD 4.1.2, 6.1)
# -----------------------------------------------------------------------------


def test_build_router_from_toml(tmp_path: Path) -> None:
    """Verify build_router_from_toml constructs router correctly."""
    from llmc.rag.enrichment_router import build_router_from_toml

    repo_root = tmp_path
    llmc = repo_root / "llmc.toml"
    llmc.write_text(
        """
[enrichment]
default_chain = "default"
enable_routing = true

[[enrichment.chain]]
name = "default-backend"
chain = "default"
provider = "ollama"
enabled = true

[enrichment.routes]
code = "default"
""",
        encoding="utf-8",
    )

    router = build_router_from_toml(repo_root, env={})
    assert router.enable_routing is True
    assert router.routes.get("code") == "default"
    assert router.log_dir == repo_root / "logs"


def test_build_router_disable_routing_env(tmp_path: Path) -> None:
    """Verify LLMC_ENRICH_DISABLE_ROUTING=1 forces routing off."""
    from llmc.rag.enrichment_router import build_router_from_toml

    repo_root = tmp_path
    llmc = repo_root / "llmc.toml"
    llmc.write_text(
        """
[enrichment]
default_chain = "default"
enable_routing = true

[[enrichment.chain]]
name = "default-backend"
chain = "default"
provider = "ollama"
enabled = true

[enrichment.routes]
code = "code_chain"
""",
        encoding="utf-8",
    )

    # With env override
    router = build_router_from_toml(repo_root, env={"LLMC_ENRICH_DISABLE_ROUTING": "1"})
    assert router.enable_routing is False  # Forced off by env


def test_router_max_tier_filtering() -> None:
    """Verify max_tier filters backend specs correctly."""
    from llmc.rag.enrichment_router import EnrichmentRouter

    backend_7b = EnrichmentBackendSpec(
        name="qwen-7b", chain="default", provider="ollama", routing_tier="7b"
    )
    backend_14b = EnrichmentBackendSpec(
        name="qwen-14b", chain="default", provider="ollama", routing_tier="14b"
    )
    config = EnrichmentConfig(
        default_chain="default",
        concurrency=1,
        cooldown_seconds=0,
        batch_size=5,
        max_retries_per_span=3,
        enforce_latin1_enrichment=True,
        chains={"default": [backend_7b, backend_14b]},
    )

    # Router with max_tier="7b" should filter out 14b backend
    router = EnrichmentRouter(
        config=config,
        enable_routing=False,
        routes=None,
        max_tier="7b",
    )

    slice_view = EnrichmentSliceView(
        span_hash="sha256:test",
        file_path=Path("test.py"),
        start_line=1,
        end_line=10,
        content_type="code",
        classifier_confidence=0.9,
        approx_token_count=100,
    )
    decision = router.choose_chain(slice_view)

    # Should only have 7b backend
    assert len(decision.backend_specs) == 1
    assert decision.backend_specs[0].routing_tier == "7b"
    assert decision.routing_tier == "7b"
