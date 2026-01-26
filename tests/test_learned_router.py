"""Tests for LearnedRouter fallback behavior."""
from llmc.routing.learned_router import (
    INTENT_CODE_LOOKUP,
    INTENT_CONCEPT_EXPLORATION,
    INTENT_MIXED,
    LearnedRouter,
    get_learned_router,
)


class TestLearnedRouterFallback:
    """Test suite for LearnedRouter heuristic fallback."""

    def test_fallback_code_lookup(self):
        """Should identify code lookup queries."""
        router = LearnedRouter()
        
        intent, confidence = router.predict("where is the function definition")
        assert intent == INTENT_CODE_LOOKUP
        assert confidence > 0.5

    def test_fallback_concept_exploration(self):
        """Should identify concept/docs queries."""
        router = LearnedRouter()
        
        intent, confidence = router.predict("how to configure the system")
        assert intent == INTENT_CONCEPT_EXPLORATION
        assert confidence > 0.5

    def test_fallback_mixed_intent(self):
        """Should return mixed for ambiguous queries."""
        router = LearnedRouter()
        
        intent, confidence = router.predict("something random")
        assert intent == INTENT_MIXED
        assert confidence == 0.5

    def test_decide_route_code(self):
        """decide_route should return correct structure for code."""
        router = LearnedRouter()
        
        result = router.decide_route("where is search_spans defined")
        assert result["route_name"] == "code"
        assert result["intent"] == INTENT_CODE_LOOKUP
        assert "confidence" in result
        assert "reasons" in result

    def test_decide_route_docs(self):
        """decide_route should return correct structure for docs."""
        router = LearnedRouter()
        
        result = router.decide_route("explain how routing works")
        assert result["route_name"] == "docs"
        assert result["intent"] == INTENT_CONCEPT_EXPLORATION

    def test_no_model_graceful(self):
        """Should work gracefully with no model path."""
        router = LearnedRouter(model_path=None)
        intent, _ = router.predict("test query")
        assert intent in [INTENT_CODE_LOOKUP, INTENT_CONCEPT_EXPLORATION, INTENT_MIXED]

    def test_nonexistent_model_path(self):
        """Should fall back when model path doesn't exist."""
        router = LearnedRouter(model_path="/nonexistent/path/model")
        intent, _ = router.predict("where is the code")
        assert intent == INTENT_CODE_LOOKUP  # Should still work via fallback


class TestGetLearnedRouter:
    """Tests for factory function."""

    def test_get_router_no_config(self):
        """Should create default router with no config."""
        router = get_learned_router(None)
        assert isinstance(router, LearnedRouter)

    def test_get_router_disabled(self):
        """Should return None when disabled."""
        config = {"routing": {"classifier": {"enable_learned_routing": False}}}
        router = get_learned_router(config)
        assert router is None

    def test_get_router_enabled(self):
        """Should create router when enabled."""
        config = {
            "routing": {
                "classifier": {
                    "enable_learned_routing": True,
                    "confidence_threshold": 0.9,
                }
            }
        }
        router = get_learned_router(config)
        assert isinstance(router, LearnedRouter)
        assert router.confidence_threshold == 0.9
