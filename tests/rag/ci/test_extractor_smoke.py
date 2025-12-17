import importlib.util
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest

from llmc.rag.ci.extractor_smoke import run_extractor_smoke


def test_smoke_produces_chunks_mocked(tmp_path) -> None:
    """Sample files produce > 0 chunks (Mocked Extractor)"""
    sample_dir = tmp_path / "samples"
    sample_dir.mkdir()
    (sample_dir / "test1.md").write_text("# Title\nContent")
    (sample_dir / "test2.md").write_text("# Title 2\nContent 2")

    # Mock the module tools.rag.extractors.tech_docs to avoid ImportError if mistune is missing
    mock_module = MagicMock()
    mock_extractor_cls = MagicMock()
    mock_module.TechDocsExtractor = mock_extractor_cls

    with patch.dict(sys.modules, {"llmc.rag.extractors.tech_docs": mock_module}):
        mock_instance = mock_extractor_cls.return_value
        # Mock extract to return 1 chunk per call
        mock_instance.extract.side_effect = [["chunk1"], ["chunk2"]]

        passed, results = run_extractor_smoke(str(sample_dir))

        assert passed
        assert len(results) == 2
        assert all(c > 0 for c in results.values())


def test_smoke_fails_on_zero_chunks_mocked(tmp_path) -> None:
    """Sample files produce 0 chunks (Mocked Extractor)"""
    sample_dir = tmp_path / "samples"
    sample_dir.mkdir()
    (sample_dir / "test1.md").write_text("# Title\nContent")

    mock_module = MagicMock()
    mock_extractor_cls = MagicMock()
    mock_module.TechDocsExtractor = mock_extractor_cls

    with patch.dict(sys.modules, {"llmc.rag.extractors.tech_docs": mock_module}):
        mock_instance = mock_extractor_cls.return_value
        # Mock extract to return 0 chunks
        mock_instance.extract.return_value = []

        passed, results = run_extractor_smoke(str(sample_dir))

        assert not passed
        assert results[str(sample_dir / "test1.md")] == 0


def test_smoke_real_files() -> None:
    """Test with real sample docs created in fixtures"""
    # Use absolute path relative to this test file, not CWD
    test_dir = Path(__file__).parent.parent.parent  # tests/rag/ci -> tests/rag -> tests
    sample_dir = test_dir / "fixtures" / "sample_docs"

    # Check if mistune is available before running
    if not importlib.util.find_spec("mistune"):
        pytest.skip("mistune not installed")

    passed, results = run_extractor_smoke(str(sample_dir))
    assert passed, f"Expected passed=True but got {passed}, results={results}"
    assert len(results) >= 2
    assert all(c > 0 for c in results.values())


def test_deterministic_chunks() -> None:
    """Same input = same chunk count"""
    # Use absolute path relative to this test file, not CWD
    test_dir = Path(__file__).parent.parent.parent  # tests/rag/ci -> tests/rag -> tests
    sample_dir = str(test_dir / "fixtures" / "sample_docs")

    if not importlib.util.find_spec("mistune"):
        pytest.skip("mistune not installed")

    passed1, results1 = run_extractor_smoke(sample_dir)
    passed2, results2 = run_extractor_smoke(sample_dir)

    assert passed1, f"First run failed: {results1}"
    assert results1 == results2
