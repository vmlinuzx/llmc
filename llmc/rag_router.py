"""
LLMC Intelligent Router - RAG-Powered LLM Selection

Core concept: Use RAG to understand query complexity and route to the
cheapest LLM that can handle it.

Routing tiers:
  - Local (Qwen):      Simple refactors, formatting, known patterns
  - MiniMax/Gemini:    Volume work, testing, bug hunting, standard tasks
  - Claude/GPT:        Architecture, validation, complex reasoning

The router uses RAG to:
  1. Analyze query intent and complexity
  2. Check if codebase context is needed
  3. Estimate required context window
  4. Select optimal tier based on cost/quality tradeoff
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import pathlib
from pathlib import Path

# Import your existing RAG tools
from llmc.rag.planner import generate_plan


@dataclass
class RoutingDecision:
    """Result of routing analysis."""

    tier: str  # "local", "mid", "premium"
    model: str  # Specific model name
    confidence: float  # 0-1, how confident in this decision
    rationale: list[str]  # Why this tier was chosen
    context_needed: bool  # Does query need codebase context
    estimated_tokens: int  # Estimated total tokens
    cost_estimate: float  # Estimated cost in USD
    rag_results: dict | None = None  # RAG context if needed


@dataclass
class QueryAnalysis:
    """Analysis of the incoming query."""

    intent: str  # What user wants (from RAG planner)
    complexity: str  # "simple", "medium", "complex"
    requires_reasoning: bool  # Need deep thinking?
    requires_codebase: bool  # Need code context?
    requires_validation: bool  # Need senior engineer review?
    estimated_context_tokens: int  # How much context needed
    confidence: float  # Confidence in analysis


class RAGRouter:
    """
    Smart router that uses RAG to make tier selection decisions.

    This is the production router that replaces manual tier selection
    with intelligent RAG-powered routing.
    """

    def __init__(self, repo_root: Path, config: dict | None = None):
        self.repo_root = Path(repo_root)
        self.config = config or self._default_config()

    def _default_config(self) -> dict:
        """Default routing configuration."""
        return {
            # Model definitions with costs (per 1M tokens)
            "models": {
                "local": {
                    "name": "qwen-2.5-coder-7b",
                    "input_cost": 0.0,
                    "output_cost": 0.0,
                    "context_window": 32768,
                    "strengths": ["formatting", "simple_refactor", "known_patterns"],
                },
                "mid": {
                    "name": "minimax-m2",
                    "input_cost": 0.50,
                    "output_cost": 1.50,
                    "context_window": 200000,
                    "strengths": ["testing", "volume", "bug_hunting", "standard_tasks"],
                },
                "premium": {
                    "name": "claude-sonnet-4.5",
                    "input_cost": 3.00,
                    "output_cost": 15.00,
                    "context_window": 200000,
                    "strengths": ["architecture", "validation", "complex_reasoning"],
                },
            },
            # Routing thresholds
            "thresholds": {
                "simple_task_confidence": 0.8,
                "premium_required_confidence": 0.9,
                "context_token_limit_local": 8000,
                "context_token_limit_mid": 32000,
            },
            # Task patterns that override RAG analysis
            "forced_routing": {
                "local": ["format", "add comments", "fix", "rename variable"],
                "mid": ["write tests", "generate test cases", "find bugs", "stress test"],
                "premium": ["design", "review security", "validate", "complex refactor"],
            },
        }

    def route(self, query: str, repo_root: Path | None = None) -> RoutingDecision:
        """
        Main routing decision point.

        Args:
            query: User's query/task
            repo_root: Optional override for repo root

        Returns:
            RoutingDecision with tier, model, and rationale
        """
        repo_root = repo_root or self.repo_root

        # Step 1: Check for forced routing patterns
        forced_tier = self._check_forced_routing(query)
        if forced_tier:
            return self._build_forced_decision(forced_tier, query)

        # Step 2: Analyze query with RAG
        analysis = self._analyze_query(query, repo_root)

        # Step 3: Make routing decision based on analysis
        decision = self._decide_tier(analysis, query, repo_root)

        return decision

    def _check_forced_routing(self, query: str) -> str | None:
        """Check if query matches forced routing patterns."""
        query_lower = query.lower()

        for tier, patterns in self.config["forced_routing"].items():
            for pattern in patterns:
                if pattern.lower() in query_lower:
                    return tier
        return None

    def _build_forced_decision(self, tier: str, query: str) -> RoutingDecision:
        """Build decision for forced routing."""
        model_info = self.config["models"][tier]

        return RoutingDecision(
            tier=tier,
            model=model_info["name"],
            confidence=1.0,
            rationale=[f"Forced routing: query matches {tier} pattern"],
            context_needed=False,
            estimated_tokens=1000,  # Conservative estimate
            cost_estimate=0.0 if tier == "local" else 0.01,
        )

    def _analyze_query(self, query: str, repo_root: Path) -> QueryAnalysis:
        """
        Use RAG to analyze the query.

        This is where the magic happens - RAG tells us:
        1. What the user wants (intent)
        2. How complex the task is
        3. What codebase context is needed
        4. Confidence in the analysis
        """
        try:
            # Use RAG planner to analyze query
            plan = generate_plan(query, limit=5, min_score=0.4)

            # Extract key metrics from plan
            intent = plan.get("intent", "unknown")
            confidence = plan.get("confidence", 0.5)
            spans = plan.get("spans", [])

            # Estimate context tokens needed
            estimated_tokens = sum(
                (span["lines"][1] - span["lines"][0]) * 4  # ~4 tokens per line
                for span in spans
            )

            # Determine complexity from RAG signals
            complexity = self._estimate_complexity(plan)

            # Check if we need reasoning vs just code generation
            requires_reasoning = self._requires_reasoning(query, plan)

            # Check if we need codebase context
            requires_codebase = len(spans) > 0 and confidence > 0.6

            # Check if task needs validation
            requires_validation = self._requires_validation(query, plan)

            return QueryAnalysis(
                intent=intent,
                complexity=complexity,
                requires_reasoning=requires_reasoning,
                requires_codebase=requires_codebase,
                requires_validation=requires_validation,
                estimated_context_tokens=estimated_tokens,
                confidence=confidence,
            )

        except Exception:
            # Fallback to conservative analysis
            return QueryAnalysis(
                intent="unknown",
                complexity="complex",  # Be conservative
                requires_reasoning=True,
                requires_codebase=True,
                requires_validation=False,
                estimated_context_tokens=5000,
                confidence=0.3,
            )

    def _estimate_complexity(self, plan: dict) -> str:
        """Estimate task complexity from RAG plan."""
        confidence = plan.get("confidence", 0.5)
        spans = plan.get("spans", [])
        symbols = plan.get("symbols", [])

        # High confidence + few spans = simple
        if confidence > 0.8 and len(spans) <= 3:
            return "simple"

        # Many symbols or low confidence = complex
        if len(symbols) > 10 or confidence < 0.5:
            return "complex"

        return "medium"

    def _requires_reasoning(self, query: str, plan: dict) -> bool:
        """Check if query needs deep reasoning."""
        reasoning_keywords = [
            "why",
            "how",
            "explain",
            "design",
            "architecture",
            "tradeoff",
            "should i",
            "compare",
            "evaluate",
        ]
        query_lower = query.lower()
        return any(kw in query_lower for kw in reasoning_keywords)

    def _requires_validation(self, query: str, plan: dict) -> bool:
        """Check if query needs senior engineer validation."""
        validation_keywords = [
            "validate",
            "review",
            "correct",
            "check my",
            "is this right",
            "am i doing this",
        ]
        query_lower = query.lower()
        return any(kw in query_lower for kw in validation_keywords)

    def _decide_tier(self, analysis: QueryAnalysis, query: str, repo_root: Path) -> RoutingDecision:
        """
        Make the routing decision based on analysis.

        Decision tree:
        1. If validation needed → premium
        2. If complex reasoning → premium
        3. If simple + high confidence → local
        4. If testing/bugs → mid (MiniMax strengths)
        5. Else → mid (cost-effective default)
        """
        rationale = []
        lower_query = query.lower()
        testing_keywords = (
            "test",
            "bug",
            "regression",
            "leak",
            "crash",
            "failure",
            "stress",
            "fuzz",
        )
        is_testing_task = any(
            keyword in lower_query for keyword in testing_keywords
        ) or analysis.intent in {"test", "debug", "verify"}

        # Decision: Premium tier
        if analysis.requires_validation:
            tier = "premium"
            rationale.append("Validation required - needs senior engineer review")
        elif analysis.complexity == "complex" and analysis.requires_reasoning:
            tier = "premium"
            rationale.append("Complex reasoning required")
        elif (
            analysis.estimated_context_tokens > self.config["thresholds"]["context_token_limit_mid"]
        ):
            tier = "premium"
            rationale.append(f"Large context needed ({analysis.estimated_context_tokens} tokens)")

        # Decision: Local tier
        elif analysis.complexity == "simple" and analysis.confidence > 0.8:
            tier = "local"
            rationale.append(f"Simple task with high confidence ({analysis.confidence:.2f})")
        elif not analysis.requires_codebase and analysis.complexity == "simple":
            tier = "local"
            rationale.append("Simple task without codebase context")

        # Decision: Mid tier (default for most work)
        else:
            tier = "mid"
            if is_testing_task:
                rationale.append("Testing/bug hunting - MiniMax excels here")
            else:
                rationale.append("Standard task - cost-effective tier")

        # Build final decision
        model_info = self.config["models"][tier]

        # Estimate cost
        estimated_input = analysis.estimated_context_tokens + len(query) * 4
        estimated_output = 5000  # Conservative estimate
        tokens_per_unit = 1_000_000.0
        cost = (estimated_input / tokens_per_unit) * model_info["input_cost"] + (
            estimated_output / tokens_per_unit
        ) * model_info["output_cost"]

        # Get RAG context if needed
        rag_results = None
        if analysis.requires_codebase and tier != "local":
            try:
                plan = generate_plan(query, limit=5)
                rag_results = plan
            except Exception:
                pass

        return RoutingDecision(
            tier=tier,
            model=model_info["name"],
            confidence=analysis.confidence,
            rationale=rationale,
            context_needed=analysis.requires_codebase,
            estimated_tokens=estimated_input + estimated_output,
            cost_estimate=cost,
            rag_results=rag_results,
        )


def route_query(query: str, repo_root: Path | None = None) -> RoutingDecision:
    """
    Convenience function for routing a single query.

    Usage:
        decision = route_query("Write tests for JWT validation")
        print(f"Route to: {decision.tier} ({decision.model})")
        print(f"Confidence: {decision.confidence:.2f}")
        print(f"Cost estimate: ${decision.cost_estimate:.4f}")
        for reason in decision.rationale:
            print(f"  - {reason}")
    """
    if repo_root is None:
        # Try to detect repo root
        current = Path.cwd()
        detected_root: Path | None = None
        current_path: Path | None = None
        visited = set()
        while True:
            marker = current / ".git"
            marker_parent = getattr(marker, "parent", None)
            if isinstance(marker_parent, pathlib.Path):
                current_path = marker_parent
            try:
                exists = marker.exists()
            except Exception:
                exists = False
            if exists:
                detected_root = marker_parent or current_path or pathlib.Path.cwd()
                break
            parent = getattr(current, "parent", None)
            if parent is None or parent == current or id(parent) in visited:
                break
            visited.add(id(parent))
            current = parent
        repo_root = detected_root or current_path or pathlib.Path.cwd()

    router = RAGRouter(repo_root)
    return router.route(query, repo_root)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python router.py 'your query here'")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    decision = route_query(query)

    print(
        json.dumps(
            {
                "tier": decision.tier,
                "model": decision.model,
                "confidence": decision.confidence,
                "rationale": decision.rationale,
                "context_needed": decision.context_needed,
                "estimated_tokens": decision.estimated_tokens,
                "cost_estimate": decision.cost_estimate,
            },
            indent=2,
        )
    )
