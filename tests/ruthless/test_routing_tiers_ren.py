import pytest

from llmc.rag.config_enrichment import (
    EnrichmentBackendSpec,
    EnrichmentConfigError,
    _parse_backend_spec,
    filter_chain_for_tier,
)


def test_routing_tier_arbitrary_strings():
    """Test that arbitrary strings are accepted as routing tiers."""
    spec_8b = EnrichmentBackendSpec(name="test-8b", routing_tier="8b", provider="ollama")
    spec_weird = EnrichmentBackendSpec(name="test-weird", routing_tier="super-mega-model-v1", provider="ollama")
    spec_empty = EnrichmentBackendSpec(name="test-empty", routing_tier="", provider="ollama")
    spec_spaces = EnrichmentBackendSpec(name="test-spaces", routing_tier="  spaced  ", provider="ollama")
    
    chain = [spec_8b, spec_weird, spec_empty, spec_spaces]

    # Test matching
    assert filter_chain_for_tier(chain, "8b") == [spec_8b]
    assert filter_chain_for_tier(chain, "super-mega-model-v1") == [spec_weird]
    assert filter_chain_for_tier(chain, "") == [spec_empty]
    assert filter_chain_for_tier(chain, "  spaced  ") == [spec_spaces]
    
    # Test mismatch
    assert filter_chain_for_tier(chain, "nonexistent") == []
    assert filter_chain_for_tier(chain, "8B") == [] # Case sensitive check

def test_routing_tier_none_fallback():
    """Test that None falls back to 7b (legacy behavior)."""
    spec_none = EnrichmentBackendSpec(name="test-none", routing_tier=None, provider="ollama")
    spec_7b = EnrichmentBackendSpec(name="test-7b", routing_tier="7b", provider="ollama")
    
    chain = [spec_none, spec_7b]
    
    # Requesting "7b" should get both
    filtered = filter_chain_for_tier(chain, "7b")
    assert spec_none in filtered
    assert spec_7b in filtered
    
    # Requesting something else should get neither (unless it matches something else)
    assert filter_chain_for_tier(chain, "other") == []

def test_parse_backend_spec_tier_conversion():
    """Test that parsing handles non-string types gracefully by converting."""
    # Int
    raw_int = {"name": "t1", "provider": "ollama", "routing_tier": 123}
    spec_int = _parse_backend_spec(raw_int, default_chain="default")
    assert spec_int.routing_tier == "123"
    
    # Float
    raw_float = {"name": "t2", "provider": "ollama", "routing_tier": 1.5}
    spec_float = _parse_backend_spec(raw_float, default_chain="default")
    assert spec_float.routing_tier == "1.5"
    
    # Bool
    raw_bool = {"name": "t3", "provider": "ollama", "routing_tier": True}
    spec_bool = _parse_backend_spec(raw_bool, default_chain="default")
    assert spec_bool.routing_tier == "True"

def test_parse_backend_spec_invalid_provider():
    """Sanity check validation."""
    with pytest.raises(EnrichmentConfigError):
        _parse_backend_spec({"name": "bad", "provider": "unsupported"}, default_chain="default")
