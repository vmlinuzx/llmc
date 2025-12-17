#!/usr/bin/env python3
"""
Unit tests for MAASL facade and PolicyRegistry.

Tests:
- ResourceClass and ResourceDescriptor
- PolicyRegistry resource resolution
- call_with_stomp_guard() coordination
- Error handling and telemetry
"""

import threading

import pytest

from llmc_mcp.maasl import (
    MAASL,
    DbBusyError,
    DocgenStaleError,
    MaaslInternalError,
    PolicyRegistry,
    ResourceBusyError,
    ResourceClass,
    ResourceDescriptor,
    StaleVersionError,
)


class TestResourceClass:
    """Test ResourceClass dataclass."""

    def test_creation(self):
        """Test ResourceClass instantiation."""
        rc = ResourceClass(
            name="TEST",
            concurrency="mutex",
            lock_scope="file",
            lease_ttl_sec=30,
            max_wait_ms=500,
            batch_max_wait_ms=3000,
            stomp_strategy="fail_closed",
        )

        assert rc.name == "TEST"
        assert rc.concurrency == "mutex"
        assert rc.lock_scope == "file"


class TestPolicyRegistry:
    """Test PolicyRegistry."""

    def test_builtin_classes(self):
        """Test built-in resource class definitions."""
        registry = PolicyRegistry()

        # All built-in classes should be present
        assert "CRIT_CODE" in registry.classes
        assert "CRIT_DB" in registry.classes
        assert "MERGE_META" in registry.classes
        assert "IDEMP_DOCS" in registry.classes

        # Verify CRIT_CODE config
        crit_code = registry.get_resource_class("CRIT_CODE")
        assert crit_code.concurrency == "mutex"
        assert crit_code.lock_scope == "file"
        assert crit_code.lease_ttl_sec == 30
        assert crit_code.max_wait_ms == 500
        assert crit_code.stomp_strategy == "fail_closed"

    def test_get_resource_class_invalid(self):
        """Test getting invalid resource class."""
        registry = PolicyRegistry()

        with pytest.raises(ValueError, match="Unknown resource class"):
            registry.get_resource_class("INVALID")

    def test_compute_resource_key(self):
        """Test resource key computation."""
        registry = PolicyRegistry()

        # File-scoped resource
        desc_code = ResourceDescriptor(
            resource_class="CRIT_CODE",
            identifier="/path/to/file.py",
        )
        assert registry.compute_resource_key(desc_code) == "code:/path/to/file.py"

        # DB-scoped resource
        desc_db = ResourceDescriptor(
            resource_class="CRIT_DB",
            identifier="rag",
        )
        assert registry.compute_resource_key(desc_db) == "db:rag"

        # Graph-scoped resource
        desc_graph = ResourceDescriptor(
            resource_class="MERGE_META",
            identifier="main",
        )
        assert registry.compute_resource_key(desc_graph) == "graph:main"

        # Repo-scoped resource
        desc_docs = ResourceDescriptor(
            resource_class="IDEMP_DOCS",
            identifier="repo",
        )
        assert registry.compute_resource_key(desc_docs) == "docgen:repo"

    def test_get_max_wait_ms(self):
        """Test max wait time based on mode."""
        registry = PolicyRegistry()
        crit_code = registry.get_resource_class("CRIT_CODE")

        # Interactive mode
        assert registry.get_max_wait_ms(crit_code, "interactive") == 500

        # Batch mode
        assert registry.get_max_wait_ms(crit_code, "batch") == 3000

    def test_config_overrides(self):
        """Test configuration overrides."""
        config = {
            "resource.CRIT_CODE": {
                "lease_ttl_sec": 60,
                "interactive_max_wait_ms": 1000,
            }
        }

        registry = PolicyRegistry(config=config)
        crit_code = registry.get_resource_class("CRIT_CODE")

        # Overrides applied
        assert crit_code.lease_ttl_sec == 60
        assert crit_code.max_wait_ms == 1000
        # Default preserved
        assert crit_code.batch_max_wait_ms == 3000


class TestMAASL:
    """Test MAASL facade."""

    def test_simple_operation(self):
        """Test basic call_with_stomp_guard."""
        maasl = MAASL()

        result_holder = {"value": None}

        def op():
            result_holder["value"] = "success"
            return "success"

        resource = ResourceDescriptor(
            resource_class="CRIT_CODE",
            identifier="/test/file.py",
        )

        result = maasl.call_with_stomp_guard(
            op=op,
            resources=[resource],
            intent="test_operation",
            mode="interactive",
            agent_id="agent1",
            session_id="session1",
        )

        assert result == "success"
        assert result_holder["value"] == "success"

    def test_multiple_resources_sorted(self):
        """Test multiple resources are locked in sorted order."""
        maasl = MAASL()

        lock_order = []

        # Override acquire to track order
        original_acquire = maasl.lock_manager.acquire

        def tracking_acquire(*args, **kwargs):
            lock_order.append(kwargs["resource_key"])
            return original_acquire(*args, **kwargs)

        maasl.lock_manager.acquire = tracking_acquire

        def op():
            return "done"

        # Resources in reverse alphabetical order
        resources = [
            ResourceDescriptor("CRIT_CODE", "/zeta.py"),
            ResourceDescriptor("CRIT_CODE", "/alpha.py"),
            ResourceDescriptor("CRIT_CODE", "/beta.py"),
        ]

        maasl.call_with_stomp_guard(
            op=op,
            resources=resources,
            intent="test_sort",
            mode="interactive",
            agent_id="agent1",
            session_id="session1",
        )

        # Should be acquired in sorted order
        assert lock_order == [
            "code:/alpha.py",
            "code:/beta.py",
            "code:/zeta.py",
        ]

    @pytest.mark.allow_sleep
    def test_lock_contention(self):
        """Test behavior when lock is busy."""
        maasl = MAASL()

        resource = ResourceDescriptor(
            resource_class="CRIT_CODE",
            identifier="/test/contended.py",
        )

        # First verify basic locking works
        # Agent 1 acquires lock synchronously
        acquired_event = threading.Event()
        release_event = threading.Event()

        def op1():
            acquired_event.set()  # Signal that we have the lock
            release_event.wait(timeout=2.0)  # Wait for signal to release
            return "agent1"

        # Start agent 1 in background
        thread1_result = []

        def run_agent1():
            try:
                result = maasl.call_with_stomp_guard(
                    op=op1,
                    resources=[resource],
                    intent="agent1_op",
                    mode="interactive",
                    agent_id="agent1",
                    session_id="session1",
                )
                thread1_result.append(("success", result))
            except Exception as e:
                thread1_result.append(("error", e))

        thread1 = threading.Thread(target=run_agent1)
        thread1.start()

        # Wait for agent1 to acquire lock
        assert acquired_event.wait(timeout=1.0), "Agent1 didn't acquire lock"

        # Now agent 2 should fail to acquire
        def op2():
            return "agent2"

        # Should timeout because agent1 holds the lock
        with pytest.raises(ResourceBusyError) as exc_info:
            maasl.call_with_stomp_guard(
                op=op2,
                resources=[resource],
                intent="agent2_op",
                mode="interactive",
                agent_id="agent2",
                session_id="session2",
            )

        err = exc_info.value
        assert err.resource_key == "code:/test/contended.py"
        assert err.holder_agent_id == "agent1"

        # Release agent1
        release_event.set()
        thread1.join(timeout=2.0)
        assert thread1_result[0][0] == "success"
        assert thread1_result[0][1] == "agent1"

    def test_exception_in_operation(self):
        """Test exception handling when op() raises."""
        maasl = MAASL()

        def op():
            raise ValueError("Test error")

        resource = ResourceDescriptor(
            resource_class="CRIT_CODE",
            identifier="/test/file.py",
        )

        with pytest.raises(MaaslInternalError) as exc_info:
            maasl.call_with_stomp_guard(
                op=op,
                resources=[resource],
                intent="failing_op",
                mode="interactive",
                agent_id="agent1",
                session_id="session1",
            )

        err = exc_info.value
        assert "Test error" in str(err)
        assert isinstance(err.original_exception, ValueError)

        # Lock should be released despite exception
        snapshot = maasl.lock_manager.snapshot()
        assert len(snapshot) == 0

    def test_lock_released_on_success(self):
        """Test locks are released after successful operation."""
        maasl = MAASL()

        def op():
            return "done"

        resource = ResourceDescriptor(
            resource_class="CRIT_CODE",
            identifier="/test/file.py",
        )

        maasl.call_with_stomp_guard(
            op=op,
            resources=[resource],
            intent="test_op",
            mode="interactive",
            agent_id="agent1",
            session_id="session1",
        )

        # All locks should be released
        snapshot = maasl.lock_manager.snapshot()
        assert len(snapshot) == 0

    def test_lock_released_on_error(self):
        """Test locks are released after operation failure."""
        maasl = MAASL()

        def op():
            raise DbBusyError("Test DB error")

        resource = ResourceDescriptor(
            resource_class="CRIT_DB",
            identifier="rag",
        )

        with pytest.raises(DbBusyError):
            maasl.call_with_stomp_guard(
                op=op,
                resources=[resource],
                intent="test_db_op",
                mode="interactive",
                agent_id="agent1",
                session_id="session1",
            )

        # All locks should be released
        snapshot = maasl.lock_manager.snapshot()
        assert len(snapshot) == 0


class TestExceptionHierarchy:
    """Test MAASL exception classes."""

    def test_db_busy_error(self):
        """Test DbBusyError."""
        err = DbBusyError("Transaction timeout", sqlite_error="SQLITE_BUSY")
        assert err.description == "Transaction timeout"
        assert err.sqlite_error == "SQLITE_BUSY"

    def test_docgen_stale_error(self):
        """Test DocgenStaleError."""
        err = DocgenStaleError(
            file="/test/file.py",
            expected_hash="abc123",
            got_hash="def456",
        )
        assert err.file == "/test/file.py"
        assert err.expected_hash == "abc123"
        assert err.got_hash == "def456"

    def test_stale_version_error(self):
        """Test StaleVersionError."""
        err = StaleVersionError(
            file="/test/file.py",
            expected_version="v1",
            current_version="v2",
        )
        assert err.file == "/test/file.py"
        assert err.expected_version == "v1"
        assert err.current_version == "v2"

    def test_maasl_internal_error(self):
        """Test MaaslInternalError."""
        original = ValueError("Original error")
        err = MaaslInternalError("Wrapped error", original_exception=original)
        assert err.message == "Wrapped error"
        assert err.original_exception is original
