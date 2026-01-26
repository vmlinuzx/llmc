from unittest.mock import patch

from llmc.rag.scoring import Scorer


class TestScorer:
    @patch("llmc.rag.scoring.load_config")
    def test_load_defaults(self, mock_load_config):
        mock_load_config.return_value = {}
        scorer = Scorer()

        assert scorer.config["code_boost"] == 0.08
        assert scorer.config["doc_penalty"] == -0.06
        assert scorer.config["enable_intent_detection"] is True
        assert ".py" in scorer.config["code_extensions"]

    @patch("llmc.rag.scoring.load_config")
    def test_load_config_override(self, mock_load_config):
        mock_load_config.return_value = {
            "scoring": {
                "code_boost": 0.5,
                "code_extensions": [".custom"],
                "enable_intent_detection": False
            }
        }
        scorer = Scorer()

        assert scorer.config["code_boost"] == 0.5
        assert ".custom" in scorer.config["code_extensions"]
        assert ".py" not in scorer.config["code_extensions"]
        assert scorer.config["enable_intent_detection"] is False

    def test_intent_detection(self):
        scorer = Scorer()
        # Default is enabled

        assert scorer.detect_intent("how to use mcp") == "docs"
        assert scorer.detect_intent("function to parse json") == "code"
        assert scorer.detect_intent("import os") == "code"
        assert scorer.detect_intent("random string") == "neutral"
        assert scorer.detect_intent("camelCaseVariable") == "code"
        assert scorer.detect_intent("snake_case_variable") == "code"

    def test_intent_detection_disabled(self):
        with patch("llmc.rag.scoring.load_config") as mock_load:
            mock_load.return_value = {"scoring": {"enable_intent_detection": False}}
            scorer = Scorer()
            assert scorer.detect_intent("how to use mcp") == "neutral"

    def test_score_extension_neutral(self):
        scorer = Scorer()

        # Code boost
        assert scorer.score_extension("main.py", "neutral") == 0.08
        # Doc penalty
        assert scorer.score_extension("README.md", "neutral") == -0.06
        # Test penalty (overrides code boost)
        assert scorer.score_extension("test_main.py", "neutral") == -0.08
        # Neutral
        assert scorer.score_extension("image.png", "neutral") == 0.0

    def test_score_extension_intent(self):
        scorer = Scorer()

        # Intent: docs
        # Code should be penalized, Docs boosted
        assert scorer.score_extension("main.py", "docs") == -0.05
        assert scorer.score_extension("README.md", "docs") == 0.10

        # Intent: code
        # Code boost amplified, Doc penalty amplified
        assert scorer.score_extension("main.py", "code") > 0.08  # 0.08 * 1.5 = 0.12
        assert scorer.score_extension("README.md", "code") < -0.06 # -0.06 * 1.5 = -0.09

    def test_score_filename_match(self):
        scorer = Scorer()

        assert scorer.score_filename_match("config", "config.py") == 0.15 # Stem match
        assert scorer.score_filename_match("config.py", "config.py") == 0.20 # Exact match
        assert scorer.score_filename_match("con", "config.py") == 0.05 # Partial match
        assert scorer.score_filename_match("xyz", "config.py") == 0.0
