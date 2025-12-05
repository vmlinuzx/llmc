
from tools.rag.config_enrichment import (
    EnrichmentBackendSpec,
    _parse_backend_spec,
    filter_chain_for_tier,
)


class TestRoutingTierFreedomRen:
    """Ruthless verification of routing_tier freedom."""

    def test_arbitrary_tier_allowed(self):
        """Test that any string is accepted as a tier."""
        raw = {
            "name": "test-backend",
            "provider": "ollama",
            "routing_tier": "garbage_tier_9000"
        }
        spec = _parse_backend_spec(raw, default_chain="default")
        assert spec.routing_tier == "garbage_tier_9000"

    def test_tier_filtering_exact_match(self):
        """Test that filtering finds our arbitrary tier."""
        spec1 = EnrichmentBackendSpec(
            name="b1", chain="c1", provider="ollama", routing_tier="garbage_tier_9000"
        )
        spec2 = EnrichmentBackendSpec(
            name="b2", chain="c1", provider="ollama", routing_tier="regular_7b"
        )
        
        chain = [spec1, spec2]
        filtered = filter_chain_for_tier(chain, "garbage_tier_9000")
        
        assert len(filtered) == 1
        assert filtered[0].name == "b1"

    def test_legacy_7b_behavior(self):
        """Test that routing_tier=None falls back to '7b' queries."""
        # If backend has None, it should show up when we ask for "7b"
        spec_none = EnrichmentBackendSpec(
            name="b_none", chain="c1", provider="ollama", routing_tier=None
        )
        chain = [spec_none]
        
        filtered = filter_chain_for_tier(chain, "7b")
        assert len(filtered) == 1
        assert filtered[0].name == "b_none"

    def test_no_fallback_for_other_tiers(self):
        """Test that routing_tier=None does NOT show up for other tiers."""
        spec_none = EnrichmentBackendSpec(
            name="b_none", chain="c1", provider="ollama", routing_tier=None
        )
        chain = [spec_none]
        
        # Asking for "8b" should NOT return the None backend
        filtered = filter_chain_for_tier(chain, "8b")
        assert len(filtered) == 0

    def test_numeric_tier_handling(self):
        """Test that numeric tiers in TOML/dict are converted to strings safely."""
        # If user puts `routing_tier = 70` (integer) in TOML
        raw = {
            "name": "test-backend",
            "provider": "ollama",
            "routing_tier": 70
        }
        spec = _parse_backend_spec(raw, default_chain="default")
        assert spec.routing_tier == "70"
        assert isinstance(spec.routing_tier, str)

