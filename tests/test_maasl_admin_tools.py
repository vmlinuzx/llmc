"""
Tests for MAASL Phase 7: Introspection Tools

Tests admin/debugging tools: llmc.locks, llmc.stomp_stats, llmc.docgen_status
"""

from pathlib import Path
import tempfile

import pytest

from llmc_mcp.admin_tools import maasl_docgen_status, maasl_locks, maasl_stomp_stats
from llmc_mcp.docgen_guard import DocgenCoordinator
from llmc_mcp.locks import get_lock_manager
from llmc_mcp.maasl import MAASL
from llmc_mcp.telemetry import get_telemetry_sink


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton state before each test."""
    # Just ensure telemetry is enabled, don't recreate it
    # (recreating breaks MAASL instances that hold references to old sink)
    telemetry = get_telemetry_sink()
    telemetry.enabled = True

    # Clear all locks
    lock_manager = get_lock_manager()
    with lock_manager._global_lock:
        lock_manager._locks.clear()

    yield


class TestMaaslLocks:
    """Test llmc.locks introspection tool."""

    def test_locks_empty(self):
        """Test locks listing when no locks held."""
        result = maasl_locks()

        assert result["count"] == 0
        assert result["locks"] == []
        assert "timestamp" in result

    @pytest.mark.allow_sleep
    def test_locks_single_lock(self):
        """Test locks listing with one active lock."""
        lock_manager = get_lock_manager()

        # Acquire a lock
        handle = lock_manager.acquire(
            resource_key="code:/test/file.py",
            agent_id="agent-1",
            session_id="sess-1",
            lease_ttl_sec=30,
            max_wait_ms=1000,
            mode="interactive",
        )

        try:
            result = maasl_locks()

            assert result["count"] == 1
            assert len(result["locks"]) == 1

            lock = result["locks"][0]
            assert lock["resource_key"] == "code:/test/file.py"
            assert lock["holder_agent_id"] == "agent-1"
            assert lock["holder_session_id"] == "sess-1"
            assert lock["fencing_token"] > 0
            assert lock["held_duration_ms"] >= 0
            assert lock["ttl_remaining_sec"] > 0
            assert not lock["is_expired"]
        finally:
            lock_manager.release(
                resource_key=handle.resource_key,
                agent_id="agent-1",
                session_id="sess-1",
                fencing_token=handle.fencing_token,
            )

    @pytest.mark.allow_sleep
    def test_locks_multiple_locks(self):
        """Test locks listing with multiple active locks."""
        lock_manager = get_lock_manager()

        # Acquire multiple locks
        handles = []
        for i in range(3):
            handle = lock_manager.acquire(
                resource_key=f"code:/test/file{i}.py",
                agent_id=f"agent-{i}",
                session_id=f"sess-{i}",
                lease_ttl_sec=30,
                max_wait_ms=1000,
                mode="interactive",
            )
            handles.append(handle)

        try:
            result = maasl_locks()

            assert result["count"] == 3
            assert len(result["locks"]) == 3

            # All locks should be present
            resource_keys = {lock["resource_key"] for lock in result["locks"]}
            assert resource_keys == {
                "code:/test/file0.py",
                "code:/test/file1.py",
                "code:/test/file2.py",
            }
        finally:
            for i, handle in enumerate(handles):
                lock_manager.release(
                    resource_key=handle.resource_key,
                    agent_id=f"agent-{i}",
                    session_id=f"sess-{i}",
                    fencing_token=handle.fencing_token,
                )


class TestStompStats:
    """Test llmc.stomp_stats introspection tool."""

    def test_stats_initial_state(self):
        """Test stats structure is present."""
        result = maasl_stomp_stats()

        # Stats may not be zero if other tests ran first
        assert "lock_acquisitions" in result
        assert "lock_timeouts" in result
        assert "lock_releases" in result
        assert "db_writes" in result
        assert "success" in result["db_writes"]
        assert "failed" in result["db_writes"]
        assert "graph_merges" in result
        assert "docgen_operations" in result
        assert "generated" in result["docgen_operations"]
        assert "noop" in result["docgen_operations"]
        assert "error" in result["docgen_operations"]
        assert "uptime_seconds" in result
        assert result["uptime_seconds"] >= 0

    @pytest.mark.allow_sleep
    def test_stats_lock_tracking(self):
        """Test stats track lock operations."""
        telemetry = get_telemetry_sink()

        # Get before counts
        before = maasl_stomp_stats()

        # Simulate lock operations
        telemetry.log_lock_acquired(
            resource_key="code:/test.py",
            agent_id="agent-1",
            session_id="sess-1",
            fencing_token=1,
            lease_ttl_sec=30,
            wait_ms=10.5,
        )

        telemetry.log_lock_timeout(
            resource_key="code:/busy.py",
            agent_id="agent-2",
            session_id="sess-2",
            max_wait_ms=500,
        )

        telemetry.log_lock_released(
            resource_key="code:/test.py",
            agent_id="agent-1",
            session_id="sess-1",
            fencing_token=1,
            held_duration_ms=100.0,
        )

        after = maasl_stomp_stats()

        assert after["lock_acquisitions"] == before["lock_acquisitions"] + 1
        assert after["lock_timeouts"] == before["lock_timeouts"] + 1
        assert after["lock_releases"] == before["lock_releases"] + 1

    def test_stats_db_tracking(self):
        """Test stats track DB operations."""
        telemetry = get_telemetry_sink()

        before = maasl_stomp_stats()

        # Simulate DB writes
        telemetry.log_db_write(
            agent_id="agent-1",
            session_id="sess-1",
            intent="rag_enrich",
            duration_ms=50.0,
            success=True,
        )

        telemetry.log_db_write(
            agent_id="agent-2",
            session_id="sess-2",
            intent="rag_enrich",
            duration_ms=10.0,
            success=False,
            error="DB locked",
        )

        after = maasl_stomp_stats()

        assert after["db_writes"]["success"] == before["db_writes"]["success"] + 1
        assert after["db_writes"]["failed"] == before["db_writes"]["failed"] + 1

    def test_stats_graph_tracking(self):
        """Test stats track graph merges."""
        telemetry = get_telemetry_sink()

        before = maasl_stomp_stats()

        telemetry.log_graph_merge(
            agent_id="agent-1",
            session_id="sess-1",
            nodes_added=5,
            edges_added=3,
            conflicts=1,
            duration_ms=25.0,
        )

        after = maasl_stomp_stats()

        assert after["graph_merges"] == before["graph_merges"] + 1

    def test_stats_docgen_tracking(self):
        """Test stats track docgen operations."""
        telemetry = get_telemetry_sink()

        before = maasl_stomp_stats()

        # Generated
        telemetry.log_docgen(
            file="/test/source.py",
            status="generated",
            hash_match=False,
            duration_ms=100.0,
            agent_id="agent-1",
            session_id="sess-1",
        )

        # NO-OP
        telemetry.log_docgen(
            file="/test/source.py",
            status="noop",
            hash_match=True,
            duration_ms=5.0,
            agent_id="agent-2",
            session_id="sess-2",
        )

        # Error
        telemetry.log_docgen(
            file="/test/missing.py",
            status="error",
            hash_match=False,
            duration_ms=1.0,
            agent_id="agent-3",
            session_id="sess-3",
            error="File not found",
        )

        after = maasl_stomp_stats()

        assert (
            after["docgen_operations"]["generated"]
            == before["docgen_operations"]["generated"] + 1
        )
        assert (
            after["docgen_operations"]["noop"]
            == before["docgen_operations"]["noop"] + 1
        )
        assert (
            after["docgen_operations"]["error"]
            == before["docgen_operations"]["error"] + 1
        )

    def test_stats_stomp_guard_tracking(self):
        """Test stats track stomp guard calls."""
        telemetry = get_telemetry_sink()

        before = maasl_stomp_stats()

        telemetry.log_stomp_guard_call(
            intent="write_file",
            mode="interactive",
            agent_id="agent-1",
            session_id="sess-1",
            resource_count=1,
            duration_ms=50.0,
            success=True,
        )

        telemetry.log_stomp_guard_call(
            intent="rag_enrich",
            mode="batch",
            agent_id="agent-2",
            session_id="sess-2",
            resource_count=2,
            duration_ms=10.0,
            success=False,
            error_type="ResourceBusyError",
        )

        after = maasl_stomp_stats()

        assert (
            after["stomp_guard_calls"]["success"]
            == before["stomp_guard_calls"]["success"] + 1
        )
        assert (
            after["stomp_guard_calls"]["failed"]
            == before["stomp_guard_calls"]["failed"] + 1
        )


class TestDocgenStatus:
    """Test llmc.docgen_status introspection tool."""

    def test_docgen_status_no_coordinator(self):
        """Test docgen status without coordinator."""
        result = maasl_docgen_status(coordinator=None)

        assert "error" in result
        assert result["count"] == 0
        assert result["operations"] == []

    def test_docgen_status_empty(self):
        """Test docgen status with empty history."""
        with tempfile.TemporaryDirectory() as tmpdir:
            coordinator = DocgenCoordinator(MAASL(), tmpdir)
            result = maasl_docgen_status(coordinator)

            assert result["count"] == 0
            assert result["operations"] == []
            assert result["buffer_size"] == coordinator.BUFFER_SIZE

    def test_docgen_status_with_operations(self):
        """Test docgen status with operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            source_file = repo_root / "test.py"
            source_file.write_text("def test(): pass\n")

            coordinator = DocgenCoordinator(MAASL(), tmpdir)

            # Run docgen
            coordinator.docgen_file(
                source_path=str(source_file), agent_id="agent-1", session_id="sess-1"
            )

            result = maasl_docgen_status(coordinator, limit=10)

            assert result["count"] == 1
            assert len(result["operations"]) == 1

            op = result["operations"][0]
            assert op["status"] == "generated"
            assert op["source_file"] == str(source_file)
            assert op["agent_id"] == "agent-1"
            assert op["hash"] is not None

    def test_docgen_status_limit(self):
        """Test docgen status respects limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            coordinator = DocgenCoordinator(MAASL(), tmpdir)

            # Create multiple operations
            for i in range(10):
                source_file = repo_root / f"test{i}.py"
                source_file.write_text(f"# File {i}\n")
                coordinator.docgen_file(
                    source_path=str(source_file),
                    agent_id=f"agent-{i}",
                    session_id=f"sess-{i}",
                )

            # Get limited results
            result = maasl_docgen_status(coordinator, limit=3)

            assert result["count"] == 3
            assert len(result["operations"]) == 3

            # Should be newest first
            assert result["operations"][0]["agent_id"] == "agent-9"


class TestIntegration:
    """Integration tests for introspection tools."""

    @pytest.mark.allow_sleep
    def test_end_to_end_workflow(self):
        """Test introspection tools in realistic workflow."""
        from llmc_mcp.maasl import ResourceDescriptor

        # Get initial stats
        stats_before = maasl_stomp_stats()
        initial_lock_count = stats_before["lock_acquisitions"]
        initial_release_count = stats_before["lock_releases"]
        initial_guard_success = stats_before["stomp_guard_calls"]["success"]

        # Create MAASL and perform operation
        maasl = MAASL()

        def dummy_op():
            return "success"

        result = maasl.call_with_stomp_guard(
            op=dummy_op,
            resources=[ResourceDescriptor("CRIT_CODE", "code:/example.py")],
            intent="test_operation",
            mode="interactive",
            agent_id="agent-1",
            session_id="sess-1",
        )

        assert result == "success"

        # Check stats incremented
        stats_after = maasl_stomp_stats()
        assert stats_after["lock_acquisitions"] > initial_lock_count
        assert stats_after["lock_releases"] > initial_release_count
        assert stats_after["stomp_guard_calls"]["success"] > initial_guard_success

        # Locks should be released
        locks = maasl_locks()
        assert locks["count"] == 0
