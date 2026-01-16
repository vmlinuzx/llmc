"""
Central Work Queue for event-driven enrichment processing.

This module provides a global SQLite-based work queue that aggregates pending
enrichment work across all repositories. It replaces the O(repos) polling
pattern with O(work) — workers only process items that actually need work.

Key features:
- Atomic claim/release for multi-worker safety
- Priority ordering (lower = higher priority)
- Orphan recovery for crashed workers
- WAL mode for concurrent access
- Ownership validation on complete/fail operations
"""

from __future__ import annotations

from dataclasses import dataclass
import errno
import os
from pathlib import Path
import select
import sqlite3
import time

# Default location for the global work queue
WORK_QUEUE_DB = Path.home() / ".llmc" / "work_queue.db"


class OwnershipError(Exception):
    """Raised when a worker tries to modify an item it doesn't own."""
    pass

SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_enrichments (
    id INTEGER PRIMARY KEY,
    repo_path TEXT NOT NULL,
    span_hash TEXT NOT NULL,
    file_path TEXT NOT NULL,
    priority INTEGER DEFAULT 5,
    created_at REAL NOT NULL,
    claimed_by TEXT,
    claimed_at REAL,
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    escalation_tier INTEGER DEFAULT 0,
    UNIQUE(repo_path, span_hash)
);

CREATE INDEX IF NOT EXISTS idx_pending_unclaimed 
    ON pending_enrichments(claimed_by, priority, created_at)
    WHERE claimed_by IS NULL;

CREATE INDEX IF NOT EXISTS idx_pending_repo 
    ON pending_enrichments(repo_path);

CREATE INDEX IF NOT EXISTS idx_pending_tier 
    ON pending_enrichments(escalation_tier, claimed_by)
    WHERE claimed_by IS NULL;

CREATE TABLE IF NOT EXISTS permanent_failures (
    id INTEGER PRIMARY KEY,
    repo_path TEXT NOT NULL,
    span_hash TEXT NOT NULL,
    file_path TEXT NOT NULL,
    reason TEXT,
    failed_at REAL NOT NULL
);
"""


@dataclass
class WorkItem:
    """A single work item from the queue."""
    id: int
    repo_path: str
    span_hash: str
    file_path: str
    priority: int
    created_at: float
    attempts: int
    escalation_tier: int = 0


class WorkQueue:
    """
    Central work queue for enrichment processing.
    
    Thread-safe for multiple workers via atomic SQL operations.
    Uses WAL mode for concurrent read/write access.
    
    Example:
        >>> queue = WorkQueue()
        >>> queue.push_work("/home/user/repo", "abc123", "src/main.py", priority=3)
        True
        >>> items = queue.pull_work("worker-1", limit=5)
        >>> for item in items:
        ...     process(item)
        ...     queue.complete_work(item.id)
    """
    
    def __init__(self, db_path: Path | None = None):
        """
        Initialize the work queue.
        
        Args:
            db_path: Path to SQLite database. Defaults to ~/.llmc/work_queue.db
        """
        self.db_path = db_path or WORK_QUEUE_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = self._open_db()
        self._init_schema()
        
        # Phase 2: Event Notification
        self.notify_pipe = self.db_path.parent / "run" / "work-notify"
        self._notify_fd = None
        self._ensure_pipe()
    
    def _open_db(self) -> sqlite3.Connection:
        """Open database with WAL mode for concurrent access."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_schema(self) -> None:
        """Create tables and indexes if they don't exist."""
        # AC-1.3: Idempotent migration
        try:
            self._conn.execute("ALTER TABLE pending_enrichments ADD COLUMN escalation_tier INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            # Column already exists or table doesn't exist yet (handled by SCHEMA)
            pass
        
        try:
            self._conn.execute("CREATE TABLE IF NOT EXISTS permanent_failures (id INTEGER PRIMARY KEY, repo_path TEXT NOT NULL, span_hash TEXT NOT NULL, file_path TEXT NOT NULL, reason TEXT, failed_at REAL NOT NULL)")
        except sqlite3.OperationalError:
            pass

        self._conn.executescript(SCHEMA)
        self._conn.commit()
        
    def _ensure_pipe(self) -> None:
        """Create named pipe for notifications if it doesn't exist."""
        try:
            if not self.notify_pipe.parent.exists():
                self.notify_pipe.parent.mkdir(parents=True, exist_ok=True)
            
            if not self.notify_pipe.exists():
                os.mkfifo(str(self.notify_pipe))
            elif not self.notify_pipe.is_fifo():
                # If it exists but isn't a pipe, remove and recreate
                self.notify_pipe.unlink()
                os.mkfifo(str(self.notify_pipe))
        except OSError:
            # AC-2.5: Graceful fallback if pipe unavailable
            pass

    def _notify_workers(self) -> None:
        """
        Notify waiting workers that new work is available.
        AC-2.2: writes to pipe
        """
        try:
            # Open non-blocking to avoid stalling the pusher
            fd = os.open(str(self.notify_pipe), os.O_WRONLY | os.O_NONBLOCK)
            try:
                os.write(fd, b'1')
            except OSError as e:
                if e.errno == errno.EAGAIN:
                    # Pipe full, that's fine, workers are busy/notified
                    pass
                else:
                    raise
            finally:
                os.close(fd)
        except OSError as e:
            if e.errno == errno.ENXIO:
                # No readers (workers) listening, that's fine
                pass
            elif e.errno == errno.ENOENT:
                # Pipe deleted? Try to recreate for next time
                self._ensure_pipe()
            else:
                # Other errors, just ignore to keep push_work robust
                pass

    def push_work(
        self, 
        repo_path: str, 
        span_hash: str, 
        file_path: str, 
        priority: int = 5
    ) -> bool:
        """
        Add a work item to the queue.
        
        Args:
            repo_path: Absolute path to the repository root.
            span_hash: Unique hash of the span to enrich.
            file_path: Path to file relative to repo root.
            priority: Priority level (1=highest, 10=lowest). Default 5.
        
        Returns:
            True if item was inserted, False if duplicate (already in queue).
        """
        try:
            self._conn.execute(
                """
                INSERT INTO pending_enrichments 
                    (repo_path, span_hash, file_path, priority, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (repo_path, span_hash, file_path, priority, time.time())
            )
            self._conn.commit()
            
            # AC-2.2: Notify workers
            self._notify_workers()
            
            return True
        except sqlite3.IntegrityError:
            # Duplicate (repo_path, span_hash) — already in queue
            return False
    
    def _get_item_tier(self, item_id: int) -> int:
        """Get the current escalation tier for an item."""
        cursor = self._conn.execute(
            "SELECT escalation_tier FROM pending_enrichments WHERE id = ?",
            (item_id,)
        )
        row = cursor.fetchone()
        return row["escalation_tier"] if row else 0

    def pull_work(self, worker_id: str, tier: int = 0, limit: int = 10) -> list[WorkItem]:
        """
        Atomically claim work items for processing.
        
        Items are ordered by priority (ascending) then creation time (ascending).
        Only unclaimed items are returned. Claimed items have `claimed_by` and
        `claimed_at` set atomically.
        
        Args:
            worker_id: Unique identifier for this worker (e.g., "worker-0").
            tier: Escalation tier to pull from. Default 0.
            limit: Maximum number of items to claim.
        
        Returns:
            List of WorkItem objects. May be empty if no work available.
        """
        now = time.time()
        
        # Atomic claim: UPDATE returns the rows we claimed
        cursor = self._conn.execute(
            """
            UPDATE pending_enrichments
            SET claimed_by = ?, claimed_at = ?
            WHERE id IN (
                SELECT id FROM pending_enrichments
                WHERE claimed_by IS NULL AND escalation_tier = ?
                ORDER BY priority ASC, created_at ASC
                LIMIT ?
            )
            RETURNING id, repo_path, span_hash, file_path, priority, created_at, attempts, escalation_tier
            """,
            (worker_id, now, tier, limit)
        )
        
        items = [
            WorkItem(
                id=row["id"],
                repo_path=row["repo_path"],
                span_hash=row["span_hash"],
                file_path=row["file_path"],
                priority=row["priority"],
                created_at=row["created_at"],
                attempts=row["attempts"],
                escalation_tier=row["escalation_tier"],
            )
            for row in cursor.fetchall()
        ]
        
        # Sort by priority (ascending) then created_at (ascending)
        # RETURNING doesn't preserve ORDER BY, so we sort after fetching
        items.sort(key=lambda x: (x.priority, x.created_at))
        
        self._conn.commit()
        return items
    
    def wait_for_work(self, timeout: float) -> bool:
        """
        Wait for new work notification.
        AC-2.3: wait_for_work(timeout) method using select()
        
        Args:
            timeout: Maximum time to wait in seconds.
            
        Returns:
            True if notified (work potentially available), False if timeout.
        """
        self._ensure_pipe()
        
        # Check if existing FD is stale (pipe deleted/recreated)
        if self._notify_fd is not None:
            try:
                stat_fd = os.fstat(self._notify_fd)
                stat_path = os.stat(str(self.notify_pipe))
                if stat_fd.st_ino != stat_path.st_ino:
                    os.close(self._notify_fd)
                    self._notify_fd = None
            except OSError:
                # If any error (e.g. file missing), close and reset
                try:
                    os.close(self._notify_fd)
                except OSError:
                    pass
                self._notify_fd = None
        
        try:
            if self._notify_fd is None:
                # Open O_RDWR so we don't block on open if no writers, 
                # and to prevent EOF if all writers close.
                self._notify_fd = os.open(str(self.notify_pipe), os.O_RDWR | os.O_NONBLOCK)
            
            # Wait for data
            r, _, _ = select.select([self._notify_fd], [], [], timeout)
            
            if r:
                # Drain pipe to clear signal
                try:
                    while True:
                        data = os.read(self._notify_fd, 4096)
                        if not data:
                            break
                except OSError as e:
                    if e.errno != errno.EAGAIN:
                        pass
                return True
            
            return False
            
        except OSError:
            # If pipe fails, fallback to short sleep or just return False
            # to allow polling loop to continue
            if self._notify_fd is not None:
                try:
                    os.close(self._notify_fd)
                except OSError:
                    pass
                self._notify_fd = None
            return False
    
    def complete_work(self, item_id: int, worker_id: str | None = None) -> None:
        """
        Mark a work item as complete (delete from queue).
        
        Args:
            item_id: The ID of the work item to complete.
            worker_id: The worker claiming ownership. If provided, validates
                      that this worker owns the item before completing.
        
        Raises:
            OwnershipError: If worker_id is provided and doesn't match claimed_by.
        """
        if worker_id is not None:
            cursor = self._conn.execute(
                "DELETE FROM pending_enrichments WHERE id = ? AND claimed_by = ?",
                (item_id, worker_id)
            )
            if cursor.rowcount == 0:
                self._conn.rollback()
                raise OwnershipError(
                    f"Worker '{worker_id}' does not own item {item_id} or item does not exist"
                )
        else:
            # Legacy path: no ownership check (for backwards compatibility)
            self._conn.execute(
                "DELETE FROM pending_enrichments WHERE id = ?",
                (item_id,)
            )
        self._conn.commit()
    
    def fail_work(self, item_id: int, error: str, worker_id: str | None = None, max_tier: int = 1, attempts_per_tier: int = 3) -> None:
        """
        Mark a work item as failed (available for retry or escalated).
        
        Retries at the same tier until attempts_per_tier is reached,
        then escalates to the next tier. After max_tier is exceeded
        with attempts_per_tier failures, the item is permanently failed.
        
        Args:
            item_id: The ID of the work item that failed.
            error: Error message describing the failure.
            worker_id: The worker claiming ownership. If provided, validates
                      that this worker owns the item before failing.
            max_tier: Maximum tier level (0-indexed). Default 1 means tiers 0 and 1.
            attempts_per_tier: Number of attempts at each tier before escalating.
                              Default 3 means try 3 times before moving to next tier.
        
        Raises:
            OwnershipError: If worker_id is provided and doesn't match claimed_by.
        """
        # Get current item state
        cursor = self._conn.execute(
            "SELECT claimed_by, escalation_tier, attempts FROM pending_enrichments WHERE id = ?",
            (item_id,)
        )
        row = cursor.fetchone()
        if not row:
            return  # Item doesn't exist, nothing to do
        
        current_tier = row["escalation_tier"]
        current_attempts = row["attempts"]
        
        if worker_id is not None and row["claimed_by"] != worker_id:
            raise OwnershipError(
                f"Worker '{worker_id}' does not own item {item_id} or item does not exist"
            )
        
        # Check if we should escalate or retry at same tier
        # attempts_per_tier defaults to 3 (try 3 times before escalating)
        should_escalate = (current_attempts + 1) >= attempts_per_tier
        
        if current_tier >= max_tier and should_escalate:
            # Permanently fail - move to permanent_failures then delete from queue
            cursor = self._conn.execute(
                "SELECT repo_path, span_hash, file_path FROM pending_enrichments WHERE id = ?",
                (item_id,)
            )
            row = cursor.fetchone()
            if row:
                self._conn.execute(
                    "INSERT INTO permanent_failures (repo_path, span_hash, file_path, reason, failed_at) VALUES (?, ?, ?, ?, ?)",
                    (row["repo_path"], row["span_hash"], row["file_path"], error, time.time())
                )
            
            # Delete from queue
            self._conn.execute("DELETE FROM pending_enrichments WHERE id = ?", (item_id,))
        elif should_escalate:
            # Escalate to next tier, reset attempts counter
            self._conn.execute(
                """
                UPDATE pending_enrichments
                SET claimed_by = NULL,
                    claimed_at = NULL,
                    attempts = 0,
                    escalation_tier = escalation_tier + 1,
                    last_error = ?
                WHERE id = ?
                """,
                (error, item_id)
            )
        else:
            # Retry at same tier - just increment attempts and release claim
            self._conn.execute(
                """
                UPDATE pending_enrichments
                SET claimed_by = NULL,
                    claimed_at = NULL,
                    attempts = attempts + 1,
                    last_error = ?
                WHERE id = ?
                """,
                (error, item_id)
            )
        self._conn.commit()

    def heartbeat_items(self, item_ids: list[int]) -> int:
        """
        Update claimed_at for specific items to prevent them from being orphaned.
        
        Args:
            item_ids: List of item IDs to renew.
            
        Returns:
            Number of items updated.
        """
        if not item_ids:
            return 0
            
        now = time.time()
        # Dynamically build query for list of IDs
        placeholders = ",".join("?" * len(item_ids))
        cursor = self._conn.execute(  # nosec B608
            f"""
            UPDATE pending_enrichments
            SET claimed_at = ?
            WHERE id IN ({placeholders})
            """,
            (now, *item_ids)
        )
        count = cursor.rowcount
        self._conn.commit()
        return count
    
    def orphan_recovery(self, timeout_seconds: int = 600) -> int:
        """
        Reclaim work items that have been claimed too long (orphaned).
        
        This handles the case where a worker crashes while processing.
        Items claimed longer than `timeout_seconds` ago are released
        back to the queue.
        
        Args:
            timeout_seconds: How long a claim can be held before considered orphaned.
                           Default is 600 seconds (10 minutes).
        
        Returns:
            Number of orphaned items reclaimed.
        """
        cutoff = time.time() - timeout_seconds
        
        cursor = self._conn.execute(
            """
            UPDATE pending_enrichments
            SET claimed_by = NULL, claimed_at = NULL
            WHERE claimed_by IS NOT NULL AND claimed_at < ?
            """,
            (cutoff,)
        )
        
        count = cursor.rowcount
        self._conn.commit()
        return count
    
    def cleanup_missing_repos(self) -> dict[str, int]:
        """
        Remove queue items for repositories that no longer exist.
        
        Scans all unique repo_paths in the queue and deletes items
        for paths that don't exist on disk.
        
        Returns:
            Dictionary of {repo_path: items_deleted} for each cleaned repo.
        """
        # Get unique repo paths
        cursor = self._conn.execute(
            "SELECT DISTINCT repo_path FROM pending_enrichments"
        )
        repo_paths = [row["repo_path"] for row in cursor.fetchall()]
        
        cleaned = {}
        for repo_path in repo_paths:
            path = Path(repo_path)
            if not path.exists():
                # Delete all items for this repo
                del_cursor = self._conn.execute(
                    "DELETE FROM pending_enrichments WHERE repo_path = ?",
                    (repo_path,)
                )
                if del_cursor.rowcount > 0:
                    cleaned[repo_path] = del_cursor.rowcount
        
        if cleaned:
            self._conn.commit()
        
        return cleaned
    
    def stats(self) -> dict:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with keys:
            - pending: Items waiting to be claimed
            - claimed: Items currently being processed
            - failed: Items with at least one failed attempt
            - total: Total items in queue
            - by_repo: Dict of repo_path -> count
            - tier_counts: Dict of tier -> count
        """
        cursor = self._conn.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE claimed_by IS NULL) as pending,
                COUNT(*) FILTER (WHERE claimed_by IS NOT NULL) as claimed,
                COUNT(*) FILTER (WHERE attempts > 0) as failed,
                COUNT(*) as total
            FROM pending_enrichments
            """
        )
        row = cursor.fetchone()
        
        # Per-repo breakdown
        by_repo_cursor = self._conn.execute(
            """
            SELECT repo_path, COUNT(*) as count
            FROM pending_enrichments
            GROUP BY repo_path
            """
        )
        by_repo = {r["repo_path"]: r["count"] for r in by_repo_cursor.fetchall()}
        
        # Per-tier breakdown
        by_tier_cursor = self._conn.execute(
            """
            SELECT escalation_tier, COUNT(*) as count
            FROM pending_enrichments
            GROUP BY escalation_tier
            """
        )
        tier_counts = {r["escalation_tier"]: r["count"] for r in by_tier_cursor.fetchall()}
        
        # Permanent failures
        fail_cursor = self._conn.execute("SELECT COUNT(*) as count FROM permanent_failures")
        perm_failed = fail_cursor.fetchone()["count"]
        
        return {
            "pending": row["pending"],
            "claimed": row["claimed"],
            "failed": row["failed"],
            "total": row["total"],
            "by_repo": by_repo,
            "tier_counts": tier_counts,
            "permanent_failures": perm_failed,
        }
    
    # Alias for compatibility with new requirements
    queue_stats = stats
    
    def clear(self) -> int:
        """
        Clear all items from the queue. USE WITH CAUTION.
        
        Returns:
            Number of items deleted.
        """
        cursor = self._conn.execute("DELETE FROM pending_enrichments")
        count = cursor.rowcount
        self._conn.commit()
        return count
    
    def list_permanent_failures(self, limit: int = 100) -> list[dict]:
        """
        List items that permanently failed enrichment.
        
        These are items that exhausted all retries at all tiers.
        Useful for debugging why certain spans couldn't be enriched.
        
        Args:
            limit: Maximum number of failures to return.
        
        Returns:
            List of dicts with keys: repo_path, span_hash, file_path, reason, failed_at
        """
        cursor = self._conn.execute(
            """
            SELECT repo_path, span_hash, file_path, reason, failed_at
            FROM permanent_failures
            ORDER BY failed_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [
            {
                "repo_path": row["repo_path"],
                "span_hash": row["span_hash"],
                "file_path": row["file_path"],
                "reason": row["reason"],
                "failed_at": row["failed_at"],
            }
            for row in cursor.fetchall()
        ]
    
    def clear_permanent_failures(self) -> int:
        """
        Clear all permanent failure records.
        
        Returns:
            Number of records deleted.
        """
        cursor = self._conn.execute("DELETE FROM permanent_failures")
        count = cursor.rowcount
        self._conn.commit()
        return count
    
    def close(self) -> None:
        """Close the database connection and notification pipe."""
        if self._notify_fd is not None:
            try:
                os.close(self._notify_fd)
            except OSError:
                pass
            self._notify_fd = None
        self._conn.close()


def calculate_priority(file_path: str) -> int:
    """
    Calculate priority based on file extension.
    Lower number = higher priority.
    
    AC-1.2:
    - Code (3): .py, .rs, .go, .js, .ts, .c, .cpp, .java
    - Docs (7): .md, .rst, .txt
    - Others (5): everything else
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext in (".py", ".rs", ".go", ".js", ".ts", ".c", ".cpp", ".java"):
        return 3
    elif ext in (".md", ".rst", ".txt"):
        return 7
    else:
        return 5


def get_queue(db_path: Path | None = None) -> WorkQueue:
    """
    Get a WorkQueue instance.
    
    This is a convenience function that creates a new WorkQueue.
    For long-running processes, prefer creating a single WorkQueue
    and reusing it.
    
    Args:
        db_path: Optional custom path for the database.
    
    Returns:
        A WorkQueue instance.
    """
    return WorkQueue(db_path)


def feed_queue_from_repos(repo_paths: list[str], limit_per_repo: int = 100) -> int:
    """
    Scan repos for pending enrichments and push to central work queue.
    
    This is the "feeder" that keeps the queue populated for pool workers.
    Should be called periodically by the daemon or pool manager.
    
    Args:
        repo_paths: List of absolute paths to registered repositories.
        limit_per_repo: Max items to pull from each repo per call.
    
    Returns:
        Total number of items added to queue.
    """
    from llmc.rag.database import Database
    from llmc.rag.config import index_path_for_write
    
    queue = WorkQueue()
    total_added = 0
    
    try:
        for repo_path in repo_paths:
            repo = Path(repo_path)
            if not repo.exists():
                continue
                
            try:
                db = Database(index_path_for_write(repo))
                pending = db.pending_enrichments(limit=limit_per_repo)
                
                for span in pending:
                    file_path = str(span.file_path) if hasattr(span, 'file_path') else str(span.get('file_path', ''))
                    span_hash = span.span_hash if hasattr(span, 'span_hash') else str(span.get('span_hash', ''))
                    priority = calculate_priority(file_path)
                    if queue.push_work(str(repo), span_hash, file_path, priority):
                        total_added += 1
                
                db.close()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to feed queue from {repo_path}: {e}")
    finally:
        queue.close()
    
    return total_added
