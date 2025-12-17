"""
Scoring logic for RAG search results.

This module handles:
1. Extension-based boosting (code vs docs)
2. Filename matching boosts
3. Intent detection (heuristic)
4. Configurable weights
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from llmc.core import load_config

logger = logging.getLogger(__name__)

# Default weights if not configured
DEFAULT_EXTENSION_BOOST = 0.08
DEFAULT_DOC_PENALTY = -0.06
DEFAULT_TEST_PENALTY = -0.08

DEFAULT_FILENAME_MATCH_EXACT = 0.20
DEFAULT_FILENAME_MATCH_STEM = 0.15
DEFAULT_FILENAME_MATCH_PARTIAL = 0.05

DEFAULT_CODE_EXTENSIONS = {
    ".py", ".ts", ".js", ".rs", ".go", ".c", ".cpp", ".h",
    ".tsx", ".jsx", ".vue", ".rb", ".java", ".kt", ".swift"
}
DEFAULT_DOC_EXTENSIONS = {".md", ".rst", ".txt"}


class Scorer:
    def __init__(self, repo_root: Path | None = None):
        self.repo_root = repo_root
        self.config = self._load_scoring_config()

    def _load_scoring_config(self) -> dict[str, Any]:
        """Load scoring configuration from llmc.toml or use defaults."""
        cfg = load_config(self.repo_root)
        scoring_cfg = cfg.get("scoring", {})

        # Merge with defaults
        return {
            "code_boost": scoring_cfg.get("code_boost", DEFAULT_EXTENSION_BOOST),
            "doc_penalty": scoring_cfg.get("doc_penalty", DEFAULT_DOC_PENALTY),
            "test_penalty": scoring_cfg.get("test_penalty", DEFAULT_TEST_PENALTY),
            "exact_match_boost": scoring_cfg.get("exact_match_boost", DEFAULT_FILENAME_MATCH_EXACT),
            "stem_match_boost": scoring_cfg.get("stem_match_boost", DEFAULT_FILENAME_MATCH_STEM),
            "partial_match_boost": scoring_cfg.get("partial_match_boost", DEFAULT_FILENAME_MATCH_PARTIAL),
            "code_extensions": set(scoring_cfg.get("code_extensions", DEFAULT_CODE_EXTENSIONS)),
            "doc_extensions": set(scoring_cfg.get("doc_extensions", DEFAULT_DOC_EXTENSIONS)),
            "enable_intent_detection": scoring_cfg.get("enable_intent_detection", True),
        }

    def detect_intent(self, query: str) -> str:
        """
        Detect if query is likely 'code' or 'docs'.

        Heuristic:
        - 'how to', 'guide', 'tutorial', 'explain' -> docs
        - 'function', 'class', 'def', 'import', camelCase, snake_case -> code
        """
        if not self.config["enable_intent_detection"]:
            return "neutral"

        q = query.lower()

        # Docs indicators
        if any(w in q for w in ["how to", "guide", "tutorial", "explain", "overview", "what is"]):
            return "docs"

        # Code indicators
        if any(w in q for w in ["function", "class", "def ", "import ", "return ", "async "]):
            return "code"

        # Check for code-like tokens (snake_case or camelCase)
        for word in query.split():
            if "_" in word and not word.startswith("_") and not word.endswith("_"):
                return "code"
            if any(c.isupper() for c in word) and any(c.islower() for c in word):
                # Simple camelCase check (imperfect but okay for heuristic)
                return "code"

        return "neutral"

    def score_extension(self, path_str: str, intent: str = "neutral") -> float:
        """
        Calculate score adjustment based on file extension and query intent.
        """
        path_lower = path_str.lower()
        ext = os.path.splitext(path_str)[1].lower()

        code_boost = self.config["code_boost"]
        doc_penalty = self.config["doc_penalty"]

        # Adjust weights based on intent
        if intent == "docs":
            code_boost = -0.05  # Penalize code if user wants docs
            doc_penalty = 0.10  # Boost docs
        elif intent == "code":
            code_boost *= 1.5   # Amplify code boost
            doc_penalty *= 1.5  # Amplify doc penalty

        # Penalize tests first
        if "test" in path_lower or "/tests/" in path_lower:
            return self.config["test_penalty"]

        if ext in self.config["code_extensions"]:
            return code_boost
        if ext in self.config["doc_extensions"]:
            return doc_penalty

        return 0.0

    def score_filename_match(self, query: str, path_str: str) -> float:
        """Calculate score boost for filename matches."""
        if not query:
            return 0.0
        q = query.strip().lower()

        basename = os.path.basename(path_str).lower()
        stem, _ = os.path.splitext(basename)

        if q == basename:
            return self.config["exact_match_boost"]
        if q == stem:
            return self.config["stem_match_boost"]
        if q in basename:
            return self.config["partial_match_boost"]
        return 0.0
