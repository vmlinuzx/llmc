"""
Concurrency control for docgen - prevents multiple simultaneous runs.
"""

import fcntl
import logging
from pathlib import Path
from typing import IO

logger = logging.getLogger(__name__)


class DocgenLock:
    """File-based lock for docgen operations.
    
    Ensures only one docgen process runs per repository at a time.
    """
    
    def __init__(self, repo_root: Path, timeout: float = 0):
        """Initialize lock.
        
        Args:
            repo_root: Absolute path to repository root
            timeout: Max seconds to wait for lock acquisition (0 = fail immediately)
        """
        self.repo_root = repo_root
        self.lock_file = repo_root / ".llmc" / "docgen.lock"
        self._lock_handle: IO | None = None
        self.timeout = timeout
    
    def acquire(self, timeout: float | None = None) -> bool:
        """Acquire the lock.
        
        Args:
            timeout: Max seconds to wait (None = use instance timeout, 0 = fail immediately)
            
        Returns:
            True if lock acquired, False otherwise
        """
        if timeout is None:
            timeout = self.timeout
            
        # Create lock directory if needed
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Open lock file
        try:
            self._lock_handle = open(self.lock_file, "w")
        except OSError as e:
            logger.error(f"Failed to open lock file: {e}")
            return False
        
        # Try to acquire exclusive lock
        try:
            if timeout > 0:
                # Blocking lock with timeout (not supported by fcntl directly)
                # For simplicity, we'll just try non-blocking
                import time
                end_time = time.time() + timeout
                while time.time() < end_time:
                    try:
                        fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        return True
                    except BlockingIOError:
                        time.sleep(0.1)
                return False
            else:
                # Non-blocking lock
                fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
        except BlockingIOError:
            # Lock already held
            self._lock_handle.close()
            self._lock_handle = None
            return False
        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            self._lock_handle.close()
            self._lock_handle = None
            return False
    
    def release(self) -> None:
        """Release the lock."""
        if self._lock_handle is None:
            return
        
        try:
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
            self._lock_handle.close()
        except Exception as e:
            logger.warning(f"Error releasing lock: {e}")
        finally:
            self._lock_handle = None
    
    def __enter__(self):
        """Context manager entry."""
        if not self.acquire():
            raise RuntimeError(
                "Failed to acquire docgen lock. "
                "Another docgen process may be running."
            )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
        return False
