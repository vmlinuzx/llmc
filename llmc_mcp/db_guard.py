#!/usr/bin/env python3
"""
Database Transaction Guard for MAASL.

Provides safe, concurrent access to SQLite databases with:
- Transaction management
- SQLite BUSY error handling
- MAASL lock integration for CRIT_DB resources
- Automatic retry with exponential backoff
"""

from __future__ import annotations

from contextlib import contextmanager
import logging
import sqlite3
import time
from typing import Iterator, Optional

from llmc_mcp.maasl import DbBusyError, get_maasl, ResourceDescriptor

logger = logging.getLogger("llmc-mcp.maasl.db_guard")


class DbTransactionManager:
    """
    SQLite transaction manager with MAASL protection.
    
    Handles:
    - BEGIN IMMEDIATE for write transactions
    - SQLite BUSY error detection and retry
    - MAASL CRIT_DB lock coordination
    - Automatic rollback on errors
    """
    
    def __init__(
        self,
        db_conn: sqlite3.Connection,
        db_name: str = "rag",
        max_retries: int = 3,
        retry_delay_ms: int = 100,
    ):
        """
        Initialize DB transaction manager.
        
        Args:
            db_conn: SQLite connection object
            db_name: Logical database name for MAASL locks (e.g., "rag")
            max_retries: Max retry attempts for SQLITE_BUSY
            retry_delay_ms: Initial retry delay in milliseconds
        """
        self.db_conn = db_conn
        self.db_name = db_name
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
    
    @contextmanager
    def write_transaction(
        self,
        agent_id: str = "unknown",
        session_id: str = "unknown",
        operation_mode: str = "interactive",
    ) -> Iterator[sqlite3.Connection]:
        """
        Context manager for protected write transactions.
        
        Acquires CRIT_DB lock, starts BEGIN IMMEDIATE transaction,
        yields connection, commits on success, rolls back on error.
        
        Args:
            agent_id: ID of calling agent
            session_id: ID of calling session
            operation_mode: "interactive" or "batch"
        
        Yields:
            SQLite connection in transaction
        
        Raises:
            DbBusyError: If database is locked and retries exhausted
        
        Example:
            >>> with mgr.write_transaction(agent_id="agent1") as conn:
            ...     conn.execute("INSERT INTO spans ...")
            ...     conn.execute("INSERT INTO enrichments ...")
        """
        # Create resource descriptor for MAASL lock
        resource = ResourceDescriptor(
            resource_class="CRIT_DB",
            identifier=self.db_name,
        )
        
        # Track if we're in the operation
        transaction_started = False
        
        # Define transaction operation that will run within MAASL guard
        def execute_and_commit():
            nonlocal transaction_started
            retries = 0
            last_error: Optional[Exception] = None
            
            while retries <= self.max_retries:
                try:
                    # Check if already in transaction
                    if self.db_conn.in_transaction:
                        # Rollback any existing transaction first
                        self.db_conn.rollback()
                    
                    # Start transaction with IMMEDIATE lock
                    self.db_conn.execute("BEGIN IMMEDIATE")
                    transaction_started = True
                    
                    # Return connection for caller to use
                    return self.db_conn
                    
                except sqlite3.OperationalError as e:
                    # Check if this is SQLITE_BUSY
                    if "database is locked" in str(e).lower():
                        last_error = e
                        retries += 1
                        
                        if retries <= self.max_retries:
                            # Exponential backoff
                            delay_ms = self.retry_delay_ms * (2 ** (retries - 1))
                            logger.warning(
                                f"SQLite BUSY (attempt {retries}/{self.max_retries}), "
                                f"retrying in {delay_ms}ms"
                            )
                            time.sleep(delay_ms / 1000.0)
                        else:
                            # Exhausted retries
                            raise DbBusyError(
                                description=f"Database locked after {self.max_retries} retries",
                                sqlite_error=str(e),
                            ) from e
                    else:
                        # Not SQLITE_BUSY - re-raise
                        raise
            
            # Should not reach here
            if last_error:
                raise last_error
        
        # Execute with MAASL protection
        maasl = get_maasl()
        
        try:
            # Acquire lock and start transaction
            conn = maasl.call_with_stomp_guard(
                op=execute_and_commit,
                resources=[resource],
                intent="db_write",
                mode=operation_mode,
                agent_id=agent_id,
                session_id=session_id,
            )
            
            # Yield connection to caller
            yield conn
            
            # Commit if no exceptions
            if transaction_started:
                self.db_conn.commit()
                
        except Exception:
            # Rollback on any error
            if transaction_started:
                self.db_conn.rollback()
            raise
    
    @contextmanager
    def read_transaction(self) -> Iterator[sqlite3.Connection]:
        """
        Context manager for read-only transactions.
        
        No MAASL lock needed for reads (readers don't block each other).
        Uses deferred BEGIN (default) for better concurrency.
        
        Yields:
            SQLite connection in read transaction
        
        Example:
            >>> with mgr.read_transaction() as conn:
            ...     rows = conn.execute("SELECT * FROM spans").fetchall()
        """
        try:
            # Deferred BEGIN (implicit, on first read)
            yield self.db_conn
            # No commit needed for read-only
        finally:
            # Ensure we're not in a transaction
            if self.db_conn.in_transaction:
                self.db_conn.rollback()


def get_db_transaction_manager(
    db_conn: sqlite3.Connection,
    db_name: str = "rag",
) -> DbTransactionManager:
    """
    Factory function for DbTransactionManager.
    
    Args:
        db_conn: SQLite connection
        db_name: Logical database name for locks
    
    Returns:
        DbTransactionManager instance
    """
    return DbTransactionManager(db_conn=db_conn, db_name=db_name)
