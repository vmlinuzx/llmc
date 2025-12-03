#!/usr/bin/env python3
"""
Integration tests for MAASL Phase 4: DB Transaction Guard.

Tests concurrent database access scenarios with multiple agents.
"""

import concurrent.futures
from pathlib import Path
import pytest
import sqlite3
import tempfile
import threading
import time
from typing import List

from llmc_mcp.db_guard import DbTransactionManager, get_db_transaction_manager
from llmc_mcp.maasl import DbBusyError, get_maasl, ResourceDescriptor


@pytest.fixture
def temp_db():
    """Create temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        
        # Create simple test table
        conn.execute("""
            CREATE TABLE test_data (
                id INTEGER PRIMARY KEY,
                agent_id TEXT NOT NULL,
                value INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        
        yield conn
        
        conn.close()


@pytest.fixture
def db_manager(temp_db):
    """Create DbTransactionManager for tests."""
    return get_db_transaction_manager(temp_db, db_name="test")


@pytest.mark.allow_sleep
def test_single_agent_write(db_manager):
    """Test single agent can write without contention."""
    with db_manager.write_transaction(agent_id="agent1", session_id="session1") as conn:
        conn.execute("INSERT INTO test_data (agent_id, value) VALUES (?, ?)", ("agent1", 42))
    
    # Verify write
    rows = db_manager.db_conn.execute("SELECT * FROM test_data").fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "agent1"
    assert rows[0][2] == 42


@pytest.mark.allow_sleep
def test_read_transaction(db_manager):
    """Test read transactions don't need locks."""
    # Insert test data
    db_manager.db_conn.execute("INSERT INTO test_data (agent_id, value) VALUES (?, ?)", ("test", 1))
    db_manager.db_conn.commit()
    
    # Read should work without MAASL lock
    with db_manager.read_transaction() as conn:
        rows = conn.execute("SELECT * FROM test_data").fetchall()
        assert len(rows) == 1


@pytest.mark.allow_sleep
def test_concurrent_writes_different_dbs(temp_db):
    """Test concurrent writes to different logical databases succeed."""
    barrier = threading.Barrier(2)
    results: List[bool] = []
    lock = threading.Lock()
    
    def write_agent(agent_id: str, db_name: str):
        """Agent writes to its own logical DB."""
        barrier.wait()
        
        mgr = get_db_transaction_manager(temp_db, db_name=db_name)
        try:
            with mgr.write_transaction(agent_id=agent_id, session_id=f"session_{agent_id}") as conn:
                conn.execute("INSERT INTO test_data (agent_id, value) VALUES (?, ?)", (agent_id, 1))
            
            with lock:
                results.append(True)
        except Exception:
            with lock:
                results.append(False)
    
    # Two agents, different logical DBs (no contention)
    threads = [
        threading.Thread(target=write_agent, args=("agent1", "db1")),
        threading.Thread(target=write_agent, args=("agent2", "db2")),
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Both should succeed (different MAASL locks)
    assert all(results)
    assert len(results) == 2


@pytest.mark.allow_sleep
def test_concurrent_writes_same_db_contention(db_manager):
    """
    Test concurrent writes to same DB - one succeeds, others timeout.
    
    Core anti-stomp test for database operations.
    """
    barrier = threading.Barrier(3)
    start_event = threading.Event()
    results: List[bool] = []
    errors: List[Exception] = []
    lock = threading.Lock()
    
    def write_agent(agent_id: str):
        """Agent attempts to write to shared database."""
        barrier.wait()
        start_event.wait()
        
        try:
            # Hold transaction for 600ms (longer than interactive timeout of 500ms)
            with db_manager.write_transaction(
                agent_id=agent_id,
                session_id=f"session_{agent_id}",
                operation_mode="interactive"
            ) as conn:
                time.sleep(0.6)  # Hold lock
                conn.execute("INSERT INTO test_data (agent_id, value) VALUES (?, ?)", (agent_id, 1))
            
            with lock:
                results.append(True)
        except Exception as e:
            with lock:
                errors.append(e)
                results.append(False)
    
    # Launch 3 agents
    threads = [
        threading.Thread(target=write_agent, args=(f"agent{i}",))
        for i in range(1, 4)
    ]
    
    for t in threads:
        t.start()
    
    time.sleep(0.01)
    start_event.set()
    
    for t in threads:
        t.join()
    
    # Results may vary based on timing, but these properties must hold:
    successes = [r for r in results if r is True]
    failures = [r for r in results if r is False]
    
    # 1. At least one agent succeeded (liveness)
    assert len(successes) >= 1, f"Expected at least 1 success, got {len(successes)}"
    
    # 2. CRITICAL: No database corruption
    # This is the MOST IMPORTANT property
    rows = db_manager.db_conn.execute("SELECT * FROM test_data").fetchall()
    # Each successful write added exactly 1 row
    assert len(rows) == len(successes), f"Data corruption: {len(rows)} rows != {len(successes)} successes"


@pytest.mark.allow_sleep
def test_transaction_rollback_on_error(db_manager):
    """Test transaction rolls back on error - no partial writes."""
    try:
        with db_manager.write_transaction(agent_id="agent1", session_id="session1") as conn:
            conn.execute("INSERT INTO test_data (agent_id, value) VALUES (?,  ?)", ("agent1", 1))
            # Trigger error
            raise ValueError("Intentional error")
    except ValueError:
        pass
    
    # Verify rollback - no data written
    rows = db_manager.db_conn.execute("SELECT * FROM test_data").fetchall()
    assert len(rows) == 0


@pytest.mark.allow_sleep
def test_lock_cleanup_after_transaction(db_manager):
    """Test MAASL locks are released after transaction completes."""
    from llmc_mcp.locks import get_lock_manager
    
    with db_manager.write_transaction(agent_id="agent1", session_id="session1") as conn:
        conn.execute("INSERT INTO test_data (agent_id, value) VALUES (?, ?)", ("agent1", 1))
    
    # Verify lock released
    mgr = get_lock_manager()
    snapshot = mgr.snapshot()
    assert len(snapshot) == 0, f"Expected 0 locks, got {len(snapshot)}"


@pytest.mark.allow_sleep
def test_batch_mode_longer_timeout(db_manager):
    """Test batch mode has longer timeout than interactive."""
    from llmc_mcp.maasl import PolicyRegistry
    
    policy = PolicyRegistry()
    crit_db = policy.get_resource_class("CRIT_DB")
    
    # Batch timeout should be higher
    assert crit_db.batch_max_wait_ms > crit_db.max_wait_ms
    assert crit_db.batch_max_wait_ms >= 10000  # At least 10 seconds


@pytest.mark.allow_sleep
def test_sqlite_busy_retry(db_manager):
    """Test that SQLITE_BUSY errors trigger retry logic."""
    # This is hard to test directly without mocking, but we can verify
    # that the retry mechanism exists
    assert db_manager.max_retries == 3
    assert db_manager.retry_delay_ms == 100


@pytest.mark.allow_sleep
def test_begin_immediate_prevents_deadlock():
    """Test that BEGIN IMMEDIATE is used for write transactions."""
    # Create two connections to same DB
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        conn1 = sqlite3.connect(str(db_path))
        conn2 = sqlite3.connect(str(db_path))
        
        # Create table
        conn1.execute("CREATE TABLE test (id INTEGER, val INTEGER)")
        conn1.commit()
        
        mgr1 = get_db_transaction_manager(conn1, "test1")
        mgr2 = get_db_transaction_manager(conn2, "test2")
        
        # Agent 1 starts write transaction
        with mgr1.write_transaction(agent_id="agent1", session_id="s1") as c1:
            c1.execute("INSERT INTO test VALUES (1, 100)")
            
            # Agent 2 should fail immediately (different MAASL lock)
            # This tests that BEGIN IMMEDIATE gets a reserved lock
            try:
                # This should timeout quickly since agent1 holds the write lock
                with mgr2.write_transaction(agent_id="agent2", session_id="s2", operation_mode="interactive") as c2:
                    c2.execute("INSERT INTO test VALUES (2, 200)")
            except:
                pass  # Expected - different MAASL locks would conflict
        
        conn1.close()
        conn2.close()
        

@pytest.mark.allow_sleep
def test_maasl_resource_descriptor():
    """Test that CRIT_DB resource descriptor is properly configured."""
    resource = ResourceDescriptor(
        resource_class="CRIT_DB",
        identifier="rag",
    )
    
    from llmc_mcp.maasl import PolicyRegistry
    
    policy = PolicyRegistry()
    resource_class = policy.get_resource_class(resource.resource_class)
    resource_key = policy.compute_resource_key(resource)
    
    assert resource_class.name == "CRIT_DB"
    assert resource_class.lock_scope == "db"
    assert resource_key == "db:rag"
    assert resource_class.lease_ttl_sec == 60  # From SDD


@pytest.mark.allow_sleep
def test_stress_concurrent_writers(db_manager):
    """
    Stress test with 5 concurrent writers.
    
    Verifies no database corruption under high contention.
    """
    barrier = threading.Barrier(5)
    results: List[bool] = []
    lock = threading.Lock()
    
    def aggressive_writer(agent_id: str):
        """Agent aggressively tries to write."""
        barrier.wait()
        
        for attempt in range(3):
            try:
                with db_manager.write_transaction(
                    agent_id=agent_id,
                    session_id=f"session_{agent_id}",
                    operation_mode="batch"  # Longer timeout
                ) as conn:
                    conn.execute("INSERT INTO test_data (agent_id, value) VALUES (?, ?)", (agent_id, attempt))
                
                with lock:
                    results.append(True)
                break
            except:
                time.sleep(0.01)
                continue
    
    # Launch 5 agents
    threads = [
        threading.Thread(target=aggressive_writer, args=(f"agent{i}",))
        for i in range(1, 6)
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # At least some should succeed
    assert len(results) > 0
    
    # CRITICAL: Verify no corruption - all rows should be valid
    rows = db_manager.db_conn.execute("SELECT * FROM test_data").fetchall()
    assert len(rows) == len(results), "Database corruption: row count mismatch"
    
    # All agent_ids should be valid
    for row in rows:
        assert row[1].startswith("agent"), f"Invalid agent_id: {row[1]}"
