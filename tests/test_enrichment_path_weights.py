from __future__ import annotations

from pathlib import Path

from llmc.enrichment import (
    FileClassifier,
    compute_final_priority,
    get_path_weight,
    load_path_weight_map,
)
from tools.rag.types import SpanWorkItem


def test_path_weight_single_match() -> None:
    config = {"src/**": 1, "**/tests/**": 6}
    weight, matched, winning = get_path_weight("src/router.py", config)
    assert weight == 1
    assert matched == ["src/**"]
    assert winning == "src/**"


def test_path_weight_collision_highest_wins() -> None:
    config = {"src/**": 1, "**/tests/**": 6}
    weight, matched, winning = get_path_weight("src/tests/test_router.py", config)
    assert weight == 6  # Highest wins
    assert "**/tests/**" in matched
    assert winning == "**/tests/**"


def test_path_weight_no_match_default() -> None:
    config: dict[str, int] = {"src/**": 1}
    weight, matched, winning = get_path_weight("random/file.txt", config)
    # Default weight is 5 when no patterns match.
    assert weight == 5
    assert matched == []
    assert winning is None


def test_priority_formula() -> None:
    assert compute_final_priority(base_priority=100, weight=1) == 100
    assert compute_final_priority(base_priority=100, weight=6) == 50
    assert compute_final_priority(base_priority=100, weight=10) == 10


def test_load_path_weight_map_basic() -> None:
    cfg = {
        "enrichment": {
            "path_weights": {
                "src/**": 1,
                "**/tests/**": 6,
            }
        }
    }
    weights = load_path_weight_map(cfg)
    assert weights == {"src/**": 1, "**/tests/**": 6}


def test_file_classifier_uses_slice_type_and_path_weights(tmp_path: Path) -> None:
    # Arrange: single work item treated as code in a test path.
    item = SpanWorkItem(
        span_hash="abc123",
        file_path=Path("src/tests/test_router.py"),
        lang="python",
        start_line=1,
        end_line=10,
        byte_start=0,
        byte_end=10,
        slice_type="code",
    )
    config = {"src/**": 1, "**/tests/**": 6}
    classifier = FileClassifier(repo_root=tmp_path, weight_config=config)

    # Act
    decision = classifier.classify_span(item)

    # Assert: highest weight wins, but base priority comes from code.
    assert decision.weight == 6
    assert decision.base_priority == 100
    assert decision.final_priority == 50
