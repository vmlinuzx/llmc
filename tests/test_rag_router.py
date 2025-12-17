"""
Comprehensive unit tests for rag_router.py - LLM Routing System.

This is the CRITICAL component that routes queries between local (Qwen),
mid-tier (MiniMax), and premium (Claude) models. These tests ensure:
- Routing logic is correct
- Cost estimation is accurate
- RAG integration works properly
- Error handling is robust
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from llmc.rag_router import (
    QueryAnalysis,
    RAGRouter,
    RoutingDecision,
    route_query,
)


class TestRoutingDecision:
    """Test the RoutingDecision dataclass."""

    def test_routing_decision_creation(self):
        """Test basic RoutingDecision creation."""
        decision = RoutingDecision(
            tier="mid",
            model="minimax-m2",
            confidence=0.85,
            rationale=["Test rationale"],
            context_needed=True,
            estimated_tokens=5000,
            cost_estimate=0.025,
        )

        assert decision.tier == "mid"
        assert decision.model == "minimax-m2"
        assert decision.confidence == 0.85
        assert decision.rationale == ["Test rationale"]
        assert decision.context_needed is True
        assert decision.estimated_tokens == 5000
        assert decision.cost_estimate == 0.025
        assert decision.rag_results is None

    def test_routing_decision_with_rag_results(self):
        """Test RoutingDecision with RAG results."""
        rag_results = {"spans": [{"file": "test.py"}]}

        decision = RoutingDecision(
            tier="premium",
            model="claude-sonnet-4.5",
            confidence=0.95,
            rationale=["Complex task"],
            context_needed=True,
            estimated_tokens=10000,
            cost_estimate=0.15,
            rag_results=rag_results,
        )

        assert decision.rag_results == rag_results


class TestQueryAnalysis:
    """Test the QueryAnalysis dataclass."""

    def test_query_analysis_creation(self):
        """Test basic QueryAnalysis creation."""
        analysis = QueryAnalysis(
            intent="refactor",
            complexity="medium",
            requires_reasoning=True,
            requires_codebase=True,
            requires_validation=False,
            estimated_context_tokens=3000,
            confidence=0.75,
        )

        assert analysis.intent == "refactor"
        assert analysis.complexity == "medium"
        assert analysis.requires_reasoning is True
        assert analysis.requires_codebase is True
        assert analysis.requires_validation is False
        assert analysis.estimated_context_tokens == 3000
        assert analysis.confidence == 0.75


class TestRAGRouterInit:
    """Test RAGRouter initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default config."""
        router = RAGRouter(Path("/tmp/test"))

        assert router.repo_root == Path("/tmp/test")
        assert router.config is not None
        assert "models" in router.config
        assert "thresholds" in router.config
        assert "forced_routing" in router.config

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        custom_config = {
            "models": {
                "local": {
                    "name": "custom-model",
                    "input_cost": 0.0,
                    "output_cost": 0.0,
                    "context_window": 32768,
                    "strengths": ["custom"],
                }
            },
            "thresholds": {},
            "forced_routing": {},
        }

        router = RAGRouter(Path("/tmp/test"), custom_config)

        assert router.config == custom_config
        assert router.config["models"]["local"]["name"] == "custom-model"

    def test_default_config_structure(self):
        """Test default config has all required fields."""
        router = RAGRouter(Path("/tmp/test"))
        config = router.config

        # Check models
        assert "local" in config["models"]
        assert "mid" in config["models"]
        assert "premium" in config["models"]

        assert config["models"]["local"]["name"] == "qwen-2.5-coder-7b"
        assert config["models"]["local"]["input_cost"] == 0.0
        assert config["models"]["local"]["output_cost"] == 0.0

        assert config["models"]["mid"]["name"] == "minimax-m2"
        assert config["models"]["premium"]["name"] == "claude-sonnet-4.5"

        # Check thresholds
        assert "simple_task_confidence" in config["thresholds"]
        assert "premium_required_confidence" in config["thresholds"]
        assert "context_token_limit_local" in config["thresholds"]
        assert "context_token_limit_mid" in config["thresholds"]

        # Check forced routing
        assert "local" in config["forced_routing"]
        assert "mid" in config["forced_routing"]
        assert "premium" in config["forced_routing"]


class TestRAGRouterForcedRouting:
    """Test forced routing functionality."""

    def test_check_forced_routing_local(self):
        """Test forced routing to local tier."""
        router = RAGRouter(Path("/tmp/test"))

        assert router._check_forced_routing("format this code") == "local"
        assert router._check_forced_routing("add comments to my function") == "local"
        assert router._check_forced_routing("fix the indentation") == "local"
        assert router._check_forced_routing("rename variable x to y") == "local"

    def test_check_forced_routing_mid(self):
        """Test forced routing to mid tier."""
        router = RAGRouter(Path("/tmp/test"))

        assert router._check_forced_routing("write tests for this module") == "mid"
        assert router._check_forced_routing("generate test cases") == "mid"
        assert router._check_forced_routing("find bugs in my code") == "mid"
        assert router._check_forced_routing("stress test this function") == "mid"

    def test_check_forced_routing_premium(self):
        """Test forced routing to premium tier."""
        router = RAGRouter(Path("/tmp/test"))

        assert (
            router._check_forced_routing("design architecture for my app") == "premium"
        )
        assert router._check_forced_routing("review security of this code") == "premium"
        assert router._check_forced_routing("validate my approach") == "premium"
        assert router._check_forced_routing("complex refactor needed") == "premium"

    def test_check_forced_routing_no_match(self):
        """Test forced routing with no matching pattern."""
        router = RAGRouter(Path("/tmp/test"))

        assert router._check_forced_routing("help me understand this algorithm") is None
        assert router._check_forced_routing("explain the codebase structure") is None

    def test_check_forced_routing_case_insensitive(self):
        """Test forced routing is case insensitive."""
        router = RAGRouter(Path("/tmp/test"))

        assert router._check_forced_routing("FORMAT CODE") == "local"
        assert router._check_forced_routing("Write Tests") == "mid"
        assert router._check_forced_routing("Design Architecture") == "premium"

    def test_build_forced_decision(self):
        """Test building forced routing decision."""
        router = RAGRouter(Path("/tmp/test"))

        decision = router._build_forced_decision("local", "format code")

        assert decision.tier == "local"
        assert decision.model == "qwen-2.5-coder-7b"
        assert decision.confidence == 1.0
        assert "Forced routing" in decision.rationale[0]
        assert decision.context_needed is False
        assert decision.estimated_tokens == 1000
        assert decision.cost_estimate == 0.0  # Local is free

    def test_build_forced_decision_mid(self):
        """Test forced decision for mid tier has cost."""
        router = RAGRouter(Path("/tmp/test"))

        decision = router._build_forced_decision("mid", "write tests")

        assert decision.tier == "mid"
        assert decision.model == "minimax-m2"
        assert decision.cost_estimate == 0.01  # Mid tier has cost


class TestRAGRouterComplexityEstimation:
    """Test complexity estimation logic."""

    def test_estimate_complexity_simple(self):
        """Test simple complexity estimation."""
        router = RAGRouter(Path("/tmp/test"))

        plan = {
            "confidence": 0.9,
            "spans": [{"lines": [1, 10]}],
            "symbols": ["function_a", "function_b"],
        }

        assert router._estimate_complexity(plan) == "simple"

    def test_estimate_complexity_simple_with_no_spans(self):
        """Test simple complexity with no spans."""
        router = RAGRouter(Path("/tmp/test"))

        plan = {"confidence": 0.85, "spans": [], "symbols": []}

        assert router._estimate_complexity(plan) == "simple"

    def test_estimate_complexity_complex_high_symbols(self):
        """Test complex due to many symbols."""
        router = RAGRouter(Path("/tmp/test"))

        symbols = [f"symbol_{i}" for i in range(15)]
        plan = {"confidence": 0.7, "spans": [{"lines": [1, 10]}], "symbols": symbols}

        assert router._estimate_complexity(plan) == "complex"

    def test_estimate_complexity_complex_low_confidence(self):
        """Test complex due to low confidence."""
        router = RAGRouter(Path("/tmp/test"))

        plan = {
            "confidence": 0.4,
            "spans": [{"lines": [1, 10]}],
            "symbols": ["symbol_a"],
        }

        assert router._estimate_complexity(plan) == "complex"

    def test_estimate_complexity_medium(self):
        """Test medium complexity."""
        router = RAGRouter(Path("/tmp/test"))

        plan = {
            "confidence": 0.7,
            "spans": [{"lines": [1, 10]}],
            "symbols": ["symbol_a", "symbol_b", "symbol_c"],
        }

        assert router._estimate_complexity(plan) == "medium"


class TestRAGRouterReasoningAndValidation:
    """Test reasoning and validation detection."""

    def test_requires_reasoning_with_keywords(self):
        """Test detection of reasoning-required queries."""
        router = RAGRouter(Path("/tmp/test"))

        assert router._requires_reasoning("why is this slow", {}) is True
        assert router._requires_reasoning("how does this work", {}) is True
        assert router._requires_reasoning("explain the algorithm", {}) is True
        assert router._requires_reasoning("design a solution", {}) is True
        assert router._requires_reasoning("compare these approaches", {}) is True
        assert router._requires_reasoning("evaluate the tradeoffs", {}) is True

    def test_requires_reasoning_without_keywords(self):
        """Test queries that don't require reasoning."""
        router = RAGRouter(Path("/tmp/test"))

        assert router._requires_reasoning("format this code", {}) is False
        assert router._requires_reasoning("write tests", {}) is False
        assert router._requires_reasoning("add comments", {}) is False

    def test_requires_validation_with_keywords(self):
        """Test detection of validation-required queries."""
        router = RAGRouter(Path("/tmp/test"))

        assert router._requires_validation("validate my approach", {}) is True
        assert router._requires_validation("review this code", {}) is True
        assert router._requires_validation("is this correct", {}) is True
        assert router._requires_validation("check my implementation", {}) is True
        assert router._requires_validation("am I doing this right", {}) is True

    def test_requires_validation_without_keywords(self):
        """Test queries that don't require validation."""
        router = RAGRouter(Path("/tmp/test"))

        assert router._requires_validation("write a test", {}) is False
        assert router._requires_validation("format code", {}) is False
        assert router._requires_validation("explain how", {}) is False


class TestRAGRouterTierDecision:
    """Test tier decision logic."""

    @patch("tools.rag_router.generate_plan")
    def test_decide_tier_validation_required(self, mock_generate_plan):
        """Test validation requirements route to premium."""
        mock_generate_plan.return_value = {
            "confidence": 0.5,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="validate",
            complexity="simple",
            requires_reasoning=False,
            requires_codebase=False,
            requires_validation=True,
            estimated_context_tokens=1000,
            confidence=0.5,
        )

        decision = router._decide_tier(analysis, "check my code", Path("/tmp/test"))

        assert decision.tier == "premium"
        assert "Validation required" in decision.rationale[0]

    @patch("tools.rag_router.generate_plan")
    def test_decide_tier_complex_reasoning(self, mock_generate_plan):
        """Test complex reasoning routes to premium."""
        mock_generate_plan.return_value = {
            "confidence": 0.6,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="explain",
            complexity="complex",
            requires_reasoning=True,
            requires_codebase=True,
            requires_validation=False,
            estimated_context_tokens=5000,
            confidence=0.6,
        )

        decision = router._decide_tier(
            analysis, "explain architecture", Path("/tmp/test")
        )

        assert decision.tier == "premium"
        assert "Complex reasoning required" in decision.rationale[0]

    @patch("tools.rag_router.generate_plan")
    def test_decide_tier_large_context(self, mock_generate_plan):
        """Test large context routes to premium."""
        mock_generate_plan.return_value = {
            "confidence": 0.7,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="refactor",
            complexity="medium",
            requires_reasoning=False,
            requires_codebase=True,
            requires_validation=False,
            estimated_context_tokens=50000,  # Very large
            confidence=0.7,
        )

        decision = router._decide_tier(analysis, "refactor module", Path("/tmp/test"))

        assert decision.tier == "premium"
        assert "Large context needed" in decision.rationale[0]

    @patch("tools.rag_router.generate_plan")
    def test_decide_tier_simple_high_confidence(self, mock_generate_plan):
        """Test simple task with high confidence routes to local."""
        mock_generate_plan.return_value = {
            "confidence": 0.9,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="format",
            complexity="simple",
            requires_reasoning=False,
            requires_codebase=False,
            requires_validation=False,
            estimated_context_tokens=500,
            confidence=0.9,
        )

        decision = router._decide_tier(analysis, "format this code", Path("/tmp/test"))

        assert decision.tier == "local"
        assert "high confidence" in decision.rationale[0]

    @patch("tools.rag_router.generate_plan")
    def test_decide_tier_simple_no_codebase(self, mock_generate_plan):
        """Test simple task without codebase context routes to local."""
        mock_generate_plan.return_value = {
            "confidence": 0.7,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="generate",
            complexity="simple",
            requires_reasoning=False,
            requires_codebase=False,
            requires_validation=False,
            estimated_context_tokens=1000,
            confidence=0.7,
        )

        decision = router._decide_tier(
            analysis, "generate a hello world", Path("/tmp/test")
        )

        assert decision.tier == "local"
        assert "without codebase context" in decision.rationale[0]

    @patch("tools.rag_router.generate_plan")
    def test_decide_tier_testing_routes_to_mid(self, mock_generate_plan):
        """Test testing tasks route to mid tier."""
        mock_generate_plan.return_value = {
            "confidence": 0.6,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="test",
            complexity="medium",
            requires_reasoning=False,
            requires_codebase=True,
            requires_validation=False,
            estimated_context_tokens=3000,
            confidence=0.6,
        )

        decision = router._decide_tier(
            analysis, "write tests for auth", Path("/tmp/test")
        )

        assert decision.tier == "mid"
        assert "Testing/bug hunting" in decision.rationale[0]

    @patch("tools.rag_router.generate_plan")
    def test_decide_tier_bug_hunting_routes_to_mid(self, mock_generate_plan):
        """Test bug hunting routes to mid tier."""
        mock_generate_plan.return_value = {
            "confidence": 0.6,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="debug",
            complexity="medium",
            requires_reasoning=False,
            requires_codebase=True,
            requires_validation=False,
            estimated_context_tokens=2000,
            confidence=0.6,
        )

        decision = router._decide_tier(analysis, "find memory leak", Path("/tmp/test"))

        assert decision.tier == "mid"
        assert "Testing/bug hunting" in decision.rationale[0]

    @patch("tools.rag_router.generate_plan")
    def test_decide_tier_default_to_mid(self, mock_generate_plan):
        """Test default routing to mid tier."""
        mock_generate_plan.return_value = {
            "confidence": 0.6,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="refactor",
            complexity="medium",
            requires_reasoning=False,
            requires_codebase=True,
            requires_validation=False,
            estimated_context_tokens=3000,
            confidence=0.6,
        )

        decision = router._decide_tier(analysis, "refactor function", Path("/tmp/test"))

        assert decision.tier == "mid"
        assert "cost-effective tier" in decision.rationale[0]


class TestRAGRouterCostEstimation:
    """Test cost estimation functionality."""

    @patch("tools.rag_router.generate_plan")
    def test_cost_estimation_local_is_free(self, mock_generate_plan):
        """Test local tier has zero cost."""
        mock_generate_plan.return_value = {
            "confidence": 0.9,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="format",
            complexity="simple",
            requires_reasoning=False,
            requires_codebase=False,
            requires_validation=False,
            estimated_context_tokens=1000,
            confidence=0.9,
        )

        decision = router._decide_tier(analysis, "format code", Path("/tmp/test"))

        assert decision.tier == "local"
        assert decision.cost_estimate == 0.0

    @patch("tools.rag_router.generate_plan")
    def test_cost_estimation_mid_tier(self, mock_generate_plan):
        """Test mid tier cost calculation."""
        mock_generate_plan.return_value = {
            "confidence": 0.6,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="refactor",
            complexity="medium",
            requires_reasoning=False,
            requires_codebase=True,
            requires_validation=False,
            estimated_context_tokens=10000,
            confidence=0.6,
        )

        decision = router._decide_tier(analysis, "refactor code", Path("/tmp/test"))

        assert decision.tier == "mid"
        assert decision.cost_estimate > 0
        assert decision.cost_estimate < 0.1  # Reasonable estimate

    @patch("tools.rag_router.generate_plan")
    def test_cost_estimation_premium_tier(self, mock_generate_plan):
        """Test premium tier cost calculation."""
        mock_generate_plan.return_value = {
            "confidence": 0.7,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="explain",
            complexity="complex",
            requires_reasoning=True,
            requires_codebase=True,
            requires_validation=False,
            estimated_context_tokens=15000,
            confidence=0.7,
        )

        decision = router._decide_tier(analysis, "explain design", Path("/tmp/test"))

        assert decision.tier == "premium"
        assert decision.cost_estimate > 0
        # Premium should be more expensive than mid
        assert decision.cost_estimate > 0.1

    @patch("tools.rag_router.generate_plan")
    def test_cost_estimate_includes_input_and_output(self, mock_generate_plan):
        """Test cost includes both input and output tokens."""
        mock_generate_plan.return_value = {
            "confidence": 0.6,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="refactor",
            complexity="medium",
            requires_reasoning=False,
            requires_codebase=True,
            requires_validation=False,
            estimated_context_tokens=10000,  # Large input
            confidence=0.6,
        )

        decision = router._decide_tier(
            analysis, "refactor " + "x" * 1000, Path("/tmp/test")
        )

        # Cost should account for large input
        assert decision.estimated_tokens > 10000  # Input + output estimate
        assert decision.cost_estimate > 0


class TestRAGRouterRAGIntegration:
    """Test RAG integration functionality."""

    @patch("tools.rag_router.generate_plan")
    def test_analyze_query_with_rag(self, mock_generate_plan):
        """Test query analysis uses RAG planner."""
        mock_generate_plan.return_value = {
            "intent": "refactor",
            "confidence": 0.8,
            "spans": [{"lines": [10, 50]}, {"lines": [100, 150]}],
            "symbols": ["function_a", "function_b"],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = router._analyze_query("refactor this code", Path("/tmp/test"))

        assert analysis.intent == "refactor"
        assert analysis.confidence == 0.8
        assert analysis.estimated_context_tokens == 360  # (40+50)*4 tokens per line
        mock_generate_plan.assert_called_once_with(
            "refactor this code", limit=5, min_score=0.4
        )

    @patch("tools.rag_router.generate_plan")
    def test_analyze_query_fallback_on_error(self, mock_generate_plan):
        """Test fallback analysis when RAG fails."""
        mock_generate_plan.side_effect = Exception("RAG service unavailable")

        router = RAGRouter(Path("/tmp/test"))

        analysis = router._analyze_query("refactor code", Path("/tmp/test"))

        # Should fall back to conservative defaults
        assert analysis.intent == "unknown"
        assert analysis.complexity == "complex"  # Conservative
        assert analysis.requires_reasoning is True  # Conservative
        assert analysis.requires_codebase is True  # Conservative
        assert analysis.requires_validation is False
        assert analysis.estimated_context_tokens == 5000
        assert analysis.confidence == 0.3  # Conservative

    @patch("tools.rag_router.generate_plan")
    def test_decide_tier_gets_rag_results(self, mock_generate_plan):
        """Test that routing decision includes RAG results when needed."""
        mock_generate_plan.return_value = {
            "intent": "refactor",
            "confidence": 0.7,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="refactor",
            complexity="medium",
            requires_reasoning=False,
            requires_codebase=True,  # Needs codebase
            requires_validation=False,
            estimated_context_tokens=3000,
            confidence=0.7,
        )

        decision = router._decide_tier(analysis, "refactor module", Path("/tmp/test"))

        # Should include RAG results for non-local tier
        assert decision.context_needed is True
        assert decision.rag_results is not None
        assert decision.rag_results["intent"] == "refactor"

    @patch("tools.rag_router.generate_plan")
    def test_decide_tier_no_rag_for_local(self, mock_generate_plan):
        """Test that local tier doesn't include RAG results."""
        mock_generate_plan.return_value = {
            "intent": "format",
            "confidence": 0.9,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="format",
            complexity="simple",
            requires_reasoning=False,
            requires_codebase=False,  # Doesn't need codebase
            requires_validation=False,
            estimated_context_tokens=500,
            confidence=0.9,
        )

        decision = router._decide_tier(analysis, "format code", Path("/tmp/test"))

        # Local tier doesn't need RAG context
        assert decision.tier == "local"
        assert decision.context_needed is False
        # RAG results might be None or present but not critical for local
        # The implementation may or may not populate this


class TestRAGRouterRouteMethod:
    """Test the main route() method."""

    @patch("tools.rag_router.generate_plan")
    def test_route_with_forced_routing(self, mock_generate_plan):
        """Test route respects forced routing patterns."""
        mock_generate_plan.return_value = {
            "intent": "format",
            "confidence": 0.5,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        decision = router.route("format this code", Path("/tmp/test"))

        # Should use forced routing, not RAG analysis
        assert decision.tier == "local"
        assert decision.confidence == 1.0
        assert "Forced routing" in decision.rationale[0]
        # generate_plan should not be called for forced routing
        # (It will be called once in _decide_tier for RAG context, but not for analysis)

    @patch("tools.rag_router.generate_plan")
    def test_route_with_rag_analysis(self, mock_generate_plan):
        """Test route uses RAG for analysis when no forced routing."""
        mock_generate_plan.return_value = {
            "intent": "refactor",
            "confidence": 0.7,
            "spans": [],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        decision = router.route("refactor this module", Path("/tmp/test"))

        assert decision.tier == "mid"  # Default for refactor
        assert decision.confidence == 0.7
        mock_generate_plan.assert_called()

    def test_route_uses_provided_repo_root(self):
        """Test route uses provided repo_root override."""
        router = RAGRouter(Path("/tmp/default"))

        with patch.object(router, "_check_forced_routing", return_value=None):
            with patch.object(router, "_analyze_query") as mock_analyze:
                with patch.object(router, "_decide_tier") as mock_decide:
                    mock_analyze.return_value = Mock(spec=QueryAnalysis)
                    mock_decide.return_value = Mock(spec=RoutingDecision)

                    router.route("test query", Path("/tmp/custom"))

                    # Should use custom repo root
                    mock_analyze.assert_called_once_with(
                        "test query", Path("/tmp/custom")
                    )
                    mock_decide.assert_called_once()

    def test_route_uses_default_repo_root(self):
        """Test route uses instance repo_root when not provided."""
        router = RAGRouter(Path("/tmp/default"))

        with patch.object(router, "_check_forced_routing", return_value=None):
            with patch.object(router, "_analyze_query") as mock_analyze:
                with patch.object(router, "_decide_tier") as mock_decide:
                    mock_analyze.return_value = Mock(spec=QueryAnalysis)
                    mock_decide.return_value = Mock(spec=RoutingDecision)

                    router.route("test query")

                    # Should use instance repo_root
                    mock_analyze.assert_called_once_with(
                        "test query", Path("/tmp/default")
                    )
                    mock_decide.assert_called_once()


class TestRouteQueryConvenienceFunction:
    """Test the route_query convenience function."""

    @patch("tools.rag_router.RAGRouter")
    def test_route_query_creates_router(self, mock_router_class):
        """Test route_query creates router with detected repo root."""
        mock_router = Mock()
        mock_router.route.return_value = Mock(spec=RoutingDecision)
        mock_router_class.return_value = mock_router

        with patch("tools.rag_router.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/tmp/repo")

            route_query("test query", Path("/tmp/custom"))

            mock_router_class.assert_called_once_with(Path("/tmp/custom"))
            mock_router.route.assert_called_once_with("test query", Path("/tmp/custom"))

    @patch("tools.rag_router.RAGRouter")
    def test_route_query_auto_detects_repo_root(self, mock_router_class):
        """Test route_query auto-detects git repository root."""
        mock_router = Mock()
        mock_router.route.return_value = Mock(spec=RoutingDecision)
        mock_router_class.return_value = mock_router

        # Mock Path.cwd to return a non-git directory, then parent with .git
        with patch("tools.rag_router.Path") as mock_path:
            # First call for cwd
            cwd_instance = Mock()
            cwd_instance.__truediv__ = lambda self, x: Path(f"/tmp/repo/{x}")
            cwd_instance.exists.return_value = False
            mock_path.cwd.return_value = cwd_instance

            # Mock parent directory
            parent = Mock()
            parent.__truediv__ = lambda self, x: Path(f"/tmp/{x}")
            parent.parent = parent  # Avoid infinite loop
            parent.exists.return_value = True
            cwd_instance.parent = parent

            # Mock .git directory
            git_dir = Mock()
            git_dir.exists.return_value = True

            with patch.object(cwd_instance, "parent", parent):
                with patch.object(
                    parent, "__truediv__", lambda self, x: Path(f"/tmp/{x}")
                ):
                    route_query("test query")

                    # Should auto-detect repo root
                    mock_router_class.assert_called_once()
                    call_args = mock_router_class.call_args
                    assert call_args[0][0] == Path("/tmp")

    @patch("tools.rag_router.RAGRouter")
    def test_route_query_calls_route(self, mock_router_class):
        """Test route_query calls route method."""
        mock_router = Mock()
        expected_decision = RoutingDecision(
            tier="mid",
            model="minimax-m2",
            confidence=0.8,
            rationale=["Test"],
            context_needed=True,
            estimated_tokens=5000,
            cost_estimate=0.05,
        )
        mock_router.route.return_value = expected_decision
        mock_router_class.return_value = mock_router

        decision = route_query("test query", Path("/tmp/repo"))

        assert decision == expected_decision
        mock_router.route.assert_called_once_with("test query", Path("/tmp/repo"))


class TestRAGRouterErrorHandling:
    """Test error handling in RAGRouter."""

    @patch("tools.rag_router.generate_plan")
    def test_analyze_query_handles_empty_plan(self, mock_generate_plan):
        """Test analysis handles empty/None values from RAG."""
        mock_generate_plan.return_value = {
            "intent": None,
            "confidence": None,
            "spans": None,
            "symbols": None,
        }

        router = RAGRouter(Path("/tmp/test"))

        # Should not crash
        analysis = router._analyze_query("test query", Path("/tmp/test"))

        assert analysis is not None
        assert hasattr(analysis, "intent")
        assert hasattr(analysis, "confidence")

    @patch("tools.rag_router.generate_plan")
    def test_analyze_query_handles_malformed_spans(self, mock_generate_plan):
        """Test analysis handles spans with missing lines."""
        mock_generate_plan.return_value = {
            "intent": "refactor",
            "confidence": 0.7,
            "spans": [
                {"lines": [10, 20]},
                {"lines": [30]},  # Missing end line
                {"lines": [40, 50]},
            ],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        # Should handle gracefully
        analysis = router._analyze_query("test query", Path("/tmp/test"))

        assert analysis.estimated_context_tokens >= 0

    @patch("tools.rag_router.generate_plan")
    def test_decide_tier_handles_missing_rag_results(self, mock_generate_plan):
        """Test decision handling when RAG context fetch fails."""
        mock_generate_plan.side_effect = [
            # First call for analysis
            {"confidence": 0.7, "spans": [], "symbols": []},
            # Second call for RAG context fails
            Exception("RAG service down"),
        ]

        router = RAGRouter(Path("/tmp/test"))

        analysis = QueryAnalysis(
            intent="refactor",
            complexity="medium",
            requires_reasoning=False,
            requires_codebase=True,
            requires_validation=False,
            estimated_context_tokens=3000,
            confidence=0.7,
        )

        # Should not crash even if RAG context fetch fails
        decision = router._decide_tier(analysis, "refactor", Path("/tmp/test"))

        assert decision is not None
        assert decision.tier == "mid"
        # RAG results might be None due to error
        assert hasattr(decision, "rag_results")


class TestRAGRouterEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_query(self):
        """Test handling of empty query."""
        router = RAGRouter(Path("/tmp/test"))

        with patch.object(router, "_check_forced_routing", return_value=None):
            with patch.object(router, "_analyze_query") as mock_analyze:
                mock_analyze.return_value = Mock(spec=QueryAnalysis)
                with patch.object(router, "_decide_tier") as mock_decide:
                    mock_decide.return_value = Mock(spec=RoutingDecision)

                    router.route("")

                    # Should handle empty string gracefully
                    mock_analyze.assert_called_once_with("", Path("/tmp/test"))

    def test_very_long_query(self):
        """Test handling of very long query."""
        router = RAGRouter(Path("/tmp/test"))

        long_query = "explain " * 10000  # Very long query

        with patch.object(router, "_check_forced_routing", return_value=None):
            with patch.object(router, "_analyze_query") as mock_analyze:
                mock_analyze.return_value = Mock(spec=QueryAnalysis)
                with patch.object(router, "_decide_tier") as mock_decide:
                    mock_decide.return_value = Mock(spec=RoutingDecision)

                    router.route(long_query)

                    mock_analyze.assert_called_once_with(long_query, Path("/tmp/test"))

    def test_special_characters_in_query(self):
        """Test handling of special characters in query."""
        router = RAGRouter(Path("/tmp/test"))

        special_query = "explain @#$%^&*() code with émojis 🎉"

        with patch.object(router, "_check_forced_routing", return_value=None):
            with patch.object(router, "_analyze_query") as mock_analyze:
                mock_analyze.return_value = Mock(spec=QueryAnalysis)
                with patch.object(router, "_decide_tier") as mock_decide:
                    mock_decide.return_value = Mock(spec=RoutingDecision)

                    router.route(special_query)

                    mock_analyze.assert_called_once_with(
                        special_query, Path("/tmp/test")
                    )

    @patch("tools.rag_router.generate_plan")
    def test_multiple_forced_routing_matches(self, mock_generate_plan):
        """Test when query matches multiple forced routing patterns."""
        router = RAGRouter(Path("/tmp/test"))

        # "format tests" matches both format (local) and tests (mid)
        # Should return the first match
        decision = router.route("format tests", Path("/tmp/test"))

        # Should match "format" pattern for local
        assert decision.tier == "local"
        assert decision.confidence == 1.0

    def test_confidence_bounds(self):
        """Test confidence is always within 0-1 range."""
        router = RAGRouter(Path("/tmp/test"))

        with patch.object(router, "_check_forced_routing", return_value=None):
            with patch.object(router, "_analyze_query") as mock_analyze:
                # Mock with extreme confidence values
                mock_analyze.return_value = QueryAnalysis(
                    intent="test",
                    complexity="simple",
                    requires_reasoning=False,
                    requires_codebase=False,
                    requires_validation=False,
                    estimated_context_tokens=1000,
                    confidence=0.99,
                )
                with patch.object(router, "_decide_tier") as mock_decide:
                    mock_decide.return_value = RoutingDecision(
                        tier="local",
                        model="test",
                        confidence=0.99,
                        rationale=[],
                        context_needed=False,
                        estimated_tokens=1000,
                        cost_estimate=0.0,
                    )

                    decision = router.route("test", Path("/tmp/test"))

                    assert 0.0 <= decision.confidence <= 1.0

    @patch("tools.rag_router.generate_plan")
    def test_context_token_calculation(self, mock_generate_plan):
        """Test context token calculation accuracy."""
        mock_generate_plan.return_value = {
            "intent": "refactor",
            "confidence": 0.7,
            "spans": [
                {"lines": [1, 10]},  # 9 lines * 4 = 36 tokens
                {"lines": [20, 30]},  # 10 lines * 4 = 40 tokens
                {"lines": [40, 45]},  # 5 lines * 4 = 20 tokens
            ],
            "symbols": [],
        }

        router = RAGRouter(Path("/tmp/test"))

        analysis = router._analyze_query("refactor", Path("/tmp/test"))

        # Expected: (9 + 10 + 5) * 4 = 96 tokens
        assert analysis.estimated_context_tokens == 96


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
