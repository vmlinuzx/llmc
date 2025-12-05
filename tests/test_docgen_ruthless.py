from pathlib import Path
from unittest.mock import MagicMock

import pytest

from llmc.docgen.locks import DocgenLock
from llmc.docgen.orchestrator import DocgenBackend, DocgenOrchestrator, DocgenResult


class MockBackend(DocgenBackend):
    def generate_for_file(self, **kwargs):
        return DocgenResult(status="generated", output_markdown="# Docs", sha256="123", reason="")

class CrashingBackend(DocgenBackend):
    def generate_for_file(self, **kwargs):
        raise RuntimeError("Backend crashed!")

@pytest.fixture
def temp_repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "test.py").write_text("print('hello')")
    return tmp_path

def test_locking_contention(temp_repo):
    """Verify that two orchestrators cannot run at the same time on the same repo."""
    lock_path = temp_repo / ".llmc" / "docgen.lock"
    
    # Simulate process A holding the lock
    with DocgenLock(temp_repo):
        assert lock_path.exists()
        
        # Process B tries to acquire
        with pytest.raises(RuntimeError):
            # Using a very short timeout for testing
            with DocgenLock(temp_repo):
                pass

def test_lock_cleanup_on_success(temp_repo):
    lock_path = temp_repo / ".llmc" / "docgen.lock"
    with DocgenLock(temp_repo):
        assert lock_path.exists()
    
    # The file might still exist, but we should be able to acquire it again
    with DocgenLock(temp_repo):
        pass

def test_orchestrator_handles_backend_crash(temp_repo):
    """Ensure a single file failure doesn't crash the batch (if orchestrated that way)
    BUT process_file doesn't catch backend exceptions, so it SHOULD crash. 
    Wait, looking at the code:
    
    # Invoke backend
    logger.info(f"Generating docs for {relative_path}")
    result = self.backend.generate_for_file(...)
    
    There is NO try/except block around self.backend.generate_for_file in process_file.
    So a backend crash should propagate.
    """
    orch = DocgenOrchestrator(
        repo_root=temp_repo,
        backend=CrashingBackend(),
        db=MagicMock(),
        output_dir="docs",
        require_rag_fresh=False
    )
    
    with pytest.raises(RuntimeError, match="Backend crashed"):
        orch.process_file(Path("src/test.py"), force=True)

from llmc.docgen.gating import resolve_doc_path


def test_write_doc_to_directory_path(temp_repo):

    """What happens if the doc path ends up being a directory?"""

    orch = DocgenOrchestrator(

        repo_root=temp_repo,

        backend=MockBackend(),

        db=MagicMock(),

        output_dir="docs",

        require_rag_fresh=False

    )

    

    # Determine exactly where the doc will go

    doc_path = resolve_doc_path(temp_repo, Path("src/test.py"), "docs")

    

    # Create a directory where the file should be

    doc_path.parent.mkdir(parents=True, exist_ok=True)

    doc_path.mkdir() # Evil setup: doc file is a dir

    

    # Orchestrator should probably fail gracefully or raise an error
    # The code does:
    # tmp_path = doc_path.with_suffix(".tmp")
    # with open(tmp_path, "w") ...
    # tmp_path.replace(doc_path)
    
    # If doc_path is a directory, replace might fail or overwrite? 
    # On Linux, replace() can overwrite a file but NOT a directory if the source is a file.
    
    # It should NOT raise, but return a result with status="skipped" and reason containing the error
    result = orch.process_file(Path("src/test.py"), force=True)
    assert result.status == "skipped"
    assert "Failed to write doc file" in result.reason

def test_stale_lock_breaking(temp_repo):
    """Verify we can break a stale lock (lock file exists but process is gone)."""
    lock_path = temp_repo / ".llmc" / "docgen.lock"
    
    # Write a fake lock file with a non-existent PID
    lock_path.parent.mkdir(exist_ok=True)
    lock_path.write_text("99999999") # unlikely PID
    
    # This should succeed if stale lock detection works
    # Note: DocgenLock needs to support this. We need to check the implementation.
    # If it doesn't, this test is a feature request/bug report.
    try:
        with DocgenLock(temp_repo):
            pass
    except RuntimeError:
        pytest.fail("Could not break stale lock")

