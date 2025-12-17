from pathlib import Path
from unittest.mock import MagicMock

import pytest

from llmc.docgen.orchestrator import DocgenBackend, DocgenOrchestrator, DocgenResult


@pytest.fixture
def temp_repo(tmp_path):
    return tmp_path


def test_batch_fault_tolerance(temp_repo):
    """Verify that batch processing is fault-tolerant - errors in individual files don't crash the batch."""
    # Setup
    (temp_repo / "src").mkdir(exist_ok=True)
    (temp_repo / "src" / "good.py").write_text("print('good')")
    (temp_repo / "src" / "bad.py").write_text("print('bad')")

    class MixedBackend(DocgenBackend):
        def generate_for_file(self, relative_path, **kwargs):
            if "bad.py" in str(relative_path):
                raise RuntimeError("Backend died on bad file")
            return DocgenResult(
                status="generated", output_markdown="OK", sha256="123", reason=""
            )

    orch = DocgenOrchestrator(
        repo_root=temp_repo,
        backend=MixedBackend(),
        db=MagicMock(),
        output_dir="docs",
        require_rag_fresh=False,
    )

    files = [Path("src/good.py"), Path("src/bad.py")]

    # After bug fix: batch should NOT crash, should continue processing
    results = orch.process_batch(files, force=True)

    # Verify we got results for BOTH files
    assert len(results) == 2

    # good.py should succeed
    assert "src/good.py" in results
    assert results["src/good.py"].status == "generated"

    # bad.py should have error status (not crash the batch)
    assert "src/bad.py" in results
    assert results["src/bad.py"].status == "error"
    assert "Backend died" in results["src/bad.py"].reason
