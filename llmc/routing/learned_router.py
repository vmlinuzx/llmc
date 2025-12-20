"""
Learned intent router using SetFit for few-shot classification.

This is a stub implementation that falls back to deterministic heuristics
when no trained model is available. Full SetFit integration is planned for
a future iteration.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Intent classes
INTENT_CODE_LOOKUP = "CODE_LOOKUP"
INTENT_CONCEPT_EXPLORATION = "CONCEPT_EXPLORATION"
INTENT_MIXED = "MIXED"


class LearnedRouter:
    """
    Router that uses a trained SetFit model for intent classification.

    Falls back to deterministic heuristics if model unavailable.
    """

    def __init__(
        self,
        model_path: Path | str | None = None,
        confidence_threshold: float = 0.85,
    ):
        self.model_path = Path(model_path) if model_path else None
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        """Load SetFit model from disk."""
        if self.model_path is None or not self.model_path.exists():
            logger.debug("No SetFit model path configured, using fallback heuristics")
            return

        try:
            from setfit import SetFitModel

            self._model = SetFitModel.from_pretrained(str(self.model_path))
            logger.info(f"Loaded SetFit router from {self.model_path}")
        except ImportError:
            logger.warning("setfit not installed, using fallback router")
        except Exception as e:
            logger.warning(f"Failed to load SetFit model: {e}")

    def predict(self, query: str) -> tuple[str, float]:
        """
        Predict intent for a query.

        Returns:
            (intent_class, confidence)
        """
        if self._model is None:
            return self._fallback_predict(query)

        try:
            # SetFit returns class labels directly
            prediction = self._model.predict([query])[0]

            # Get probabilities for confidence
            probs = self._model.predict_proba([query])[0]
            confidence = float(max(probs))

            return str(prediction), confidence

        except Exception as e:
            logger.warning(f"SetFit prediction failed: {e}")
            return self._fallback_predict(query)

    def _fallback_predict(self, query: str) -> tuple[str, float]:
        """Deterministic fallback using keyword heuristics."""
        query_lower = query.lower()

        # Code lookup indicators
        code_patterns = [
            "where is",
            "definition of",
            "function",
            "class",
            "method",
            "implemented",
            "implementation",
            "source code",
            "code for",
            ".py",
            ".ts",
            ".js",
            "def ",
            "async def",
        ]

        # Docs/concept indicators
        docs_patterns = [
            "how to",
            "what is",
            "explain",
            "documentation",
            "guide",
            "tutorial",
            "example",
            "why",
            "configure",
            "setup",
        ]

        code_score = sum(1 for p in code_patterns if p in query_lower)
        docs_score = sum(1 for p in docs_patterns if p in query_lower)

        if code_score > docs_score:
            return INTENT_CODE_LOOKUP, min(0.5 + code_score * 0.1, 0.85)
        elif docs_score > code_score:
            return INTENT_CONCEPT_EXPLORATION, min(0.5 + docs_score * 0.1, 0.85)
        else:
            return INTENT_MIXED, 0.5

    def decide_route(
        self, query: str, tool_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Router interface compatible with existing Router ABC.
        """
        intent, confidence = self.predict(query)

        # Map intent to route
        if intent == INTENT_CODE_LOOKUP:
            route_name = "code"
        elif intent == INTENT_CONCEPT_EXPLORATION:
            route_name = "docs"
        else:
            route_name = "mixed"

        return {
            "route_name": route_name,
            "confidence": confidence,
            "intent": intent,
            "reasons": [f"LearnedRouter (fallback): {intent}"],
        }


def get_learned_router(config: dict[str, Any] | None = None) -> LearnedRouter | None:
    """
    Factory function to create a LearnedRouter from config.

    Returns None if learned routing is disabled.
    """
    if config is None:
        return LearnedRouter()

    routing_cfg = config.get("routing", {}).get("classifier", {})

    if not routing_cfg.get("enable_learned_routing", False):
        return None

    model_path = routing_cfg.get("model_path")
    threshold = routing_cfg.get("confidence_threshold", 0.85)

    return LearnedRouter(model_path=model_path, confidence_threshold=threshold)
