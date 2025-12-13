import importlib.util
import sys
from unittest.mock import MagicMock, patch

import pytest

from tools.rag.ci.extractor_smoke import run_extractor_smoke


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

    with patch.dict(sys.modules, {"tools.rag.extractors.tech_docs": mock_module}):
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

    with patch.dict(sys.modules, {"tools.rag.extractors.tech_docs": mock_module}):
        mock_instance = mock_extractor_cls.return_value
        # Mock extract to return 0 chunks
        mock_instance.extract.return_value = []
        
        passed, results = run_extractor_smoke(str(sample_dir))
        
        assert not passed
        assert results[str(sample_dir / "test1.md")] == 0


def test_smoke_real_files() -> None:
    """Test with real sample docs created in fixtures"""
    sample_dir = "tests/fixtures/sample_docs"
    # Check if mistune is available before running
    if not importlib.util.find_spec("mistune"):
        pytest.skip("mistune not installed")

    # Ensure we use the REAL module here, not the mock from previous tests (patch.dict handles cleanup)
    # But just in case sys.modules caching issues? patch.dict undoes changes.
    
    passed, results = run_extractor_smoke(sample_dir)
    assert passed
    assert len(results) >= 2
    assert all(c > 0 for c in results.values())


def test_deterministic_chunks() -> None:
    """Same input = same chunk count"""
    sample_dir = "tests/fixtures/sample_docs"
    if not importlib.util.find_spec("mistune"):
        pytest.skip("mistune not installed")

    passed1, results1 = run_extractor_smoke(sample_dir)
    passed2, results2 = run_extractor_smoke(sample_dir)
    
    assert passed1
    assert results1 == results2
