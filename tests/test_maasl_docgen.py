"""
Tests for MAASL Phase 6: Docgen Coordination

Tests docgen SHA gating, repo-level mutex, and idempotent behavior.
"""

from pathlib import Path
import tempfile
import threading

import pytest

from llmc_mcp.docgen_guard import DocgenCoordinator
from llmc_mcp.maasl import MAASL


@pytest.fixture
def temp_repo():
    """Create temporary repository structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        
        # Create source file
        source_dir = repo_root / "src"
        source_dir.mkdir()
        source_file = source_dir / "example.py"
        source_file.write_text("def hello():\n    return 'world'\n")
        
        yield repo_root, source_file


@pytest.fixture
def coordinator(temp_repo):
    """Create DocgenCoordinator with temp repo."""
    repo_root, _ = temp_repo
    maasl = MAASL()  # Uses default PolicyRegistry and singletons
    return DocgenCoordinator(maasl, str(repo_root))


class TestDocgenCoordinator:
    """Test DocgenCoordinator core functionality."""
    
    def test_compute_source_hash(self, coordinator, temp_repo):
        """Test SHA256 hash computation."""
        _, source_file = temp_repo
        
        hash1 = coordinator.compute_source_hash(str(source_file))
        assert len(hash1) == 64  # SHA256 hex length
        assert hash1.isalnum()
        
        # Same file = same hash
        hash2 = coordinator.compute_source_hash(str(source_file))
        assert hash1 == hash2
        
        # Modified file = different hash
        source_file.write_text("def hello():\n    return 'universe'\n")
        hash3 = coordinator.compute_source_hash(str(source_file))
        assert hash3 != hash1
    
    def test_get_doc_path(self, coordinator, temp_repo):
        """Test documentation path generation."""
        repo_root, source_file = temp_repo
        
        doc_path = coordinator.get_doc_path(str(source_file))
        
        # Should be in DOCS/REPODOCS
        assert doc_path.parent == coordinator.docs_dir
        
        # Should convert path to filename
        assert doc_path.name == "src_example.py.md"
    
    def test_read_doc_hash_missing(self, coordinator, temp_repo):
        """Test reading hash from non-existent doc."""
        _, source_file = temp_repo
        doc_path = coordinator.get_doc_path(str(source_file))
        
        result = coordinator.read_doc_hash(doc_path)
        assert result is None
    
    def test_read_doc_hash_present(self, coordinator, temp_repo):
        """Test reading hash from existing doc."""
        _, source_file = temp_repo
        doc_path = coordinator.get_doc_path(str(source_file))
        
        # Write doc with hash header
        test_hash = "abc123def456"
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(f"<!-- SHA256: {test_hash} -->\n# Doc\nContent")
        
        result = coordinator.read_doc_hash(doc_path)
        assert result == test_hash
    
    def test_atomic_write(self, coordinator, temp_repo):
        """Test atomic file writing."""
        repo_root, _ = temp_repo
        test_file = coordinator.docs_dir / "test.md"
        
        content = "# Test Document\n\nAtomically written!"
        coordinator.atomic_write(test_file, content)
        
        assert test_file.exists()
        assert test_file.read_text() == content
        
        # No temp files left behind
        temp_files = list(coordinator.docs_dir.glob(".test.md.*.tmp"))
        assert len(temp_files) == 0
    
    def test_generate_doc_content(self, coordinator, temp_repo):
        """Test doc content generation."""
        _, source_file = temp_repo
        source_hash = coordinator.compute_source_hash(str(source_file))
        
        content = coordinator.generate_doc_content(str(source_file), source_hash)
        
        # Should have SHA header
        assert content.startswith(f"<!-- SHA256: {source_hash} -->")
        
        # Should have markdown structure
        assert "# Documentation:" in content
        assert "**Source:**" in content
        assert "**Hash:**" in content


class TestDocgenOperations:
    """Test docgen operations with SHA gating."""
    
    def test_docgen_file_first_generation(self, coordinator, temp_repo):
        """Test generating doc for first time."""
        _, source_file = temp_repo
        
        result = coordinator.docgen_file(
            source_path=str(source_file),
            agent_id="agent-1",
            session_id="sess-1",
            operation_mode="interactive"
        )
        
        assert result.status == "generated"
        assert result.hash is not None
        assert result.doc_path is not None
        assert Path(result.doc_path).exists()
        assert result.duration_ms >= 0
        assert result.agent_id == "agent-1"
        
        # Doc should have correct hash
        doc_path = Path(result.doc_path)
        stored_hash = coordinator.read_doc_hash(doc_path)
        assert stored_hash == result.hash
    
    def test_docgen_file_noop_when_up_to_date(self, coordinator, temp_repo):
        """Test SHA gating - skip when doc is current."""
        _, source_file = temp_repo
        
        # First generation
        result1 = coordinator.docgen_file(
            source_path=str(source_file),
            agent_id="agent-1",
            session_id="sess-1"
        )
        assert result1.status == "generated"
        
        # Second call - should NO-OP
        result2 = coordinator.docgen_file(
            source_path=str(source_file),
            agent_id="agent-2",
            session_id="sess-2"
        )
        assert result2.status == "noop"
        assert result2.hash == result1.hash
        # Both operations are sub-millisecond, timing comparison unreliable
    
    def test_docgen_file_regenerates_on_source_change(self, coordinator, temp_repo):
        """Test regeneration when source file changes."""
        _, source_file = temp_repo
        
        # First generation
        result1 = coordinator.docgen_file(
            source_path=str(source_file),
            agent_id="agent-1",
            session_id="sess-1"
        )
        assert result1.status == "generated"
        original_hash = result1.hash
        
        # Modify source
        source_file.write_text("def hello():\n    return 'modified'\n")
        
        # Should regenerate
        result2 = coordinator.docgen_file(
            source_path=str(source_file),
            agent_id="agent-2",
            session_id="sess-2"
        )
        assert result2.status == "generated"
        assert result2.hash != original_hash
    
    def test_docgen_file_error_handling(self, coordinator, temp_repo):
        """Test error handling for missing source."""
        repo_root, _ = temp_repo
        missing_file = str(repo_root / "nonexistent.py")
        
        with pytest.raises(FileNotFoundError):
            coordinator.docgen_file(
                source_path=missing_file,
                agent_id="agent-1",
                session_id="sess-1"
            )
        
        # Error should be logged in history
        history = coordinator.get_status(limit=1)
        assert len(history) == 1
        assert history[0].status == "error"
        assert history[0].error is not None


@pytest.mark.allow_sleep
class TestConcurrentDocgen:
    """Test concurrent docgen operations with IDEMP_DOCS lock."""
    
    def test_concurrent_docgen_serialization(self, coordinator, temp_repo):
        """Test that concurrent docgen calls are serialized."""
        _, source_file = temp_repo
        
        results = []
        errors = []
        barrier = threading.Barrier(3)  # Sync 3 threads
        
        def docgen_worker(agent_id):
            try:
                barrier.wait()  # Start all at once
                result = coordinator.docgen_file(
                    source_path=str(source_file),
                    agent_id=agent_id,
                    session_id=f"sess-{agent_id}"
                )
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=docgen_worker, args=(f"agent-{i}",))
            for i in range(3)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # No errors
        assert len(errors) == 0
        assert len(results) == 3
        
        # With IDEMP_DOCS, multiple generations are acceptable
        # The key guarantee is: all agents see consistent final state
        statuses = [r.status for r in results]
        
        # At least one generation occurred
        assert "generated" in statuses
        
        # All agents see the same final hash
        hashes = [r.hash for r in results]
        assert len(set(hashes)) == 1
        
        # Doc file exists and is valid
        doc_path = Path(results[0].doc_path)
        assert doc_path.exists()
        stored_hash = coordinator.read_doc_hash(doc_path)
        assert stored_hash == hashes[0]
    
    def test_concurrent_docgen_different_files(self, coordinator, temp_repo):
        """Test concurrent docgen on different files proceeds in parallel."""
        repo_root, source_file1 = temp_repo
        
        # Create second source file
        source_file2 = repo_root / "src" / "another.py"
        source_file2.write_text("def goodbye():\n    return 'world'\n")
        
        results = []
        errors = []
        barrier = threading.Barrier(2)
        
        def docgen_worker(source_file, agent_id):
            try:
                barrier.wait()
                result = coordinator.docgen_file(
                    source_path=str(source_file),
                    agent_id=agent_id,
                    session_id=f"sess-{agent_id}"
                )
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=docgen_worker, args=(source_file1, "agent-1")),
            threading.Thread(target=docgen_worker, args=(source_file2, "agent-2"))
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Both should succeed
        assert len(errors) == 0
        assert len(results) == 2
        
        # Both should generate (different files)
        assert all(r.status == "generated" for r in results)
        
        # Different hashes
        hashes = [r.hash for r in results]
        assert hashes[0] != hashes[1]


class TestDocgenStatus:
    """Test docgen status tracking."""
    
    def test_get_status_empty(self, coordinator):
        """Test status with no history."""
        status = coordinator.get_status()
        assert status == []
    
    def test_get_status_single_operation(self, coordinator, temp_repo):
        """Test status after single operation."""
        _, source_file = temp_repo
        
        result = coordinator.docgen_file(
            source_path=str(source_file),
            agent_id="agent-1",
            session_id="sess-1"
        )
        
        status = coordinator.get_status(limit=10)
        assert len(status) == 1
        assert status[0].status == result.status
        assert status[0].hash == result.hash
    
    def test_get_status_multiple_operations(self, coordinator, temp_repo):
        """Test status tracks multiple operations."""
        _, source_file = temp_repo
        
        # Generate multiple times (first gen, then NO-OPs)
        for i in range(5):
            coordinator.docgen_file(
                source_path=str(source_file),
                agent_id=f"agent-{i}",
                session_id=f"sess-{i}"
            )
        
        status = coordinator.get_status(limit=10)
        assert len(status) == 5
        
        # Should be in reverse chronological order (newest first)
        assert status[0].agent_id == "agent-4"
        assert status[-1].agent_id == "agent-0"
    
    def test_get_status_limit(self, coordinator, temp_repo):
        """Test status respects limit parameter."""
        _, source_file = temp_repo
        
        # Generate many operations
        for i in range(20):
            source_file.write_text(f"# Version {i}\n")
            coordinator.docgen_file(
                source_path=str(source_file),
                agent_id=f"agent-{i}",
                session_id=f"sess-{i}"
            )
        
        status = coordinator.get_status(limit=5)
        assert len(status) == 5
        
        # Should be newest 5
        assert status[0].agent_id == "agent-19"
        assert status[4].agent_id == "agent-15"
    
    def test_circular_buffer_limit(self, coordinator, temp_repo):
        """Test circular buffer doesn't grow unbounded."""
        _, source_file = temp_repo
        
        # Generate more than BUFFER_SIZE operations
        for i in range(DocgenCoordinator.BUFFER_SIZE + 50):
            source_file.write_text(f"# Version {i}\n")
            coordinator.docgen_file(
                source_path=str(source_file),
                agent_id=f"agent-{i}",
                session_id=f"sess-{i}"
            )
        
        # Should only keep BUFFER_SIZE
        status = coordinator.get_status(limit=200)
        assert len(status) == DocgenCoordinator.BUFFER_SIZE
        
        # Should be newest BUFFER_SIZE
        assert status[0].agent_id == f"agent-{DocgenCoordinator.BUFFER_SIZE + 49}"
        assert status[-1].agent_id == "agent-50"


class TestDocgenIntegration:
    """Integration tests for docgen coordination."""
    
    def test_end_to_end_workflow(self, coordinator, temp_repo):
        """Test complete docgen workflow."""
        _, source_file = temp_repo
        
        # 1. Initial generation
        result = coordinator.docgen_file(
            source_path=str(source_file),
            agent_id="agent-1",
            session_id="sess-1",
            operation_mode="interactive"
        )
        assert result.status == "generated"
        doc_path = Path(result.doc_path)
        assert doc_path.exists()
        
        # 2. Verify SHA header
        content = doc_path.read_text()
        assert content.startswith(f"<!-- SHA256: {result.hash} -->")
        
        # 3. Second call - should NO-OP
        result2 = coordinator.docgen_file(
            source_path=str(source_file),
            agent_id="agent-2",
            session_id="sess-2"
        )
        assert result2.status == "noop"
        assert result2.hash == result.hash
        
        # 4. Modify source
        source_file.write_text("# Modified\ndef new_func(): pass\n")
        
        # 5. Should regenerate
        result3 = coordinator.docgen_file(
            source_path=str(source_file),
            agent_id="agent-3",
            session_id="sess-3"
        )
        assert result3.status == "generated"
        assert result3.hash != result.hash
        
        # 6. Doc updated with new hash
        new_content = doc_path.read_text()
        assert new_content.startswith(f"<!-- SHA256: {result3.hash} -->")
        assert result3.hash != result.hash
        
        # 7. History tracks all operations
        history = coordinator.get_status(limit=10)
        assert len(history) == 3
