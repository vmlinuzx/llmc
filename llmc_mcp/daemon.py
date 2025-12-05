"""Daemon process manager for LLMC MCP server."""

from __future__ import annotations

import atexit
from collections.abc import Callable
import logging
import os
from pathlib import Path
import signal
import sys
from typing import Any

logger = logging.getLogger(__name__)


class MCPDaemon:
    """
    Daemon process manager for LLMC MCP HTTP server.

    Handles process lifecycle: daemonization, pidfile management,
    signal handling, and graceful shutdown.

    Example:
        daemon = MCPDaemon(lambda: create_http_server())
        daemon.start()  # Daemonizes and runs server
        daemon.stop()   # Stop running daemon
        daemon.status() # Check if running
    """

    PIDFILE = Path.home() / ".llmc" / "mcp-daemon.pid"
    LOGFILE = Path.home() / ".llmc" / "logs" / "mcp-daemon.log"

    def __init__(self, server_factory: Callable[[], Any]):
        """
        Initialize daemon manager.

        Args:
            server_factory: Callable that creates and returns HTTP server
        """
        self.server_factory = server_factory
        self._server: Any | None = None

    def start(self, foreground: bool = False) -> bool:
        """
        Start the daemon.

        Args:
            foreground: If True, run in foreground (don't daemonize)

        Returns:
            True if started successfully, False if already running
        """
        if self._is_running():
            logger.warning(f"Daemon already running (PID {self._get_pid()})")
            return False

        if not foreground:
            self._daemonize()

        self._write_pidfile()
        atexit.register(self._cleanup)
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        logger.info("Starting MCP daemon")
        self._server = self.server_factory()
        self._server.run()

        return True

    def stop(self) -> bool:
        """
        Stop the running daemon.

        Returns:
            True if stopped successfully, False if not running
        """
        pid = self._get_pid()
        if not pid:
            logger.warning("Daemon not running")
            return False

        logger.info(f"Stopping daemon (PID {pid})")
        try:
            os.kill(pid, signal.SIGTERM)
            self.PIDFILE.unlink(missing_ok=True)
            return True
        except ProcessLookupError:
            # Process doesn't exist - clean up stale pidfile
            logger.warning(f"Process {pid} not found (stale pidfile)")
            self.PIDFILE.unlink(missing_ok=True)
            return False
        except PermissionError:
            logger.error(f"Permission denied killing PID {pid}")
            return False

    def restart(self, foreground: bool = False) -> bool:
        """
        Restart the daemon (stop then start).

        Args:
            foreground: If True, run in foreground mode

        Returns:
            True if restarted successfully
        """
        logger.info("Restarting daemon")
        self.stop()
        # Give it a moment to shutdown
        import time

        time.sleep(1)
        return self.start(foreground=foreground)

    def status(self) -> dict[str, Any]:
        """
        Get daemon status.

        Returns:
            Dict with:
                - running: bool
                - pid: int | None
                - pidfile: str
                - logfile: str
        """
        pid = self._get_pid()
        running = self._is_running()
        return {
            "running": running,
            "pid": pid if running else None,
            "pidfile": str(self.PIDFILE),
            "logfile": str(self.LOGFILE),
        }

    def _daemonize(self) -> None:
        """
        Daemonize the process using double-fork technique.

        This detaches the process from the terminal and ensures it
        runs independently in the background.
        """
        # First fork
        try:
            pid = os.fork()
            if pid > 0:
                # Parent exits
                sys.exit(0)
        except OSError as e:
            logger.error(f"First fork failed: {e}")
            sys.exit(1)

        # Decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # Second fork
        try:
            pid = os.fork()
            if pid > 0:
                # Parent exits
                sys.exit(0)
        except OSError as e:
            logger.error(f"Second fork failed: {e}")
            sys.exit(1)

        # We're in the daemon process now
        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()

        # Ensure log directory exists
        self.LOGFILE.parent.mkdir(parents=True, exist_ok=True)

        # Redirect stdin to /dev/null
        with open("/dev/null") as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())

        # Redirect stdout and stderr to logfile
        with open(self.LOGFILE, "a") as logfile:
            os.dup2(logfile.fileno(), sys.stdout.fileno())
            os.dup2(logfile.fileno(), sys.stderr.fileno())

        logger.info("Daemon process started")

    def _is_running(self) -> bool:
        """
        Check if daemon is actually running.

        Returns:
            True if running, False otherwise
        """
        pid = self._get_pid()
        if not pid:
            return False

        try:
            # Send signal 0 (doesn't actually send signal, just checks existence)
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _get_pid(self) -> int | None:
        """
        Read PID from pidfile.

        Returns:
            PID if found, None otherwise
        """
        try:
            return int(self.PIDFILE.read_text().strip())
        except (FileNotFoundError, ValueError):
            return None

    def _write_pidfile(self) -> None:
        """Write current PID to pidfile."""
        self.PIDFILE.parent.mkdir(parents=True, exist_ok=True)
        self.PIDFILE.write_text(str(os.getpid()))
        logger.info(f"Pidfile written: {self.PIDFILE}")

    def _cleanup(self) -> None:
        """Cleanup on exit (remove pidfile)."""
        self.PIDFILE.unlink(missing_ok=True)
        logger.info("Daemon cleanup complete")

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """
        Handle termination signals.

        Args:
            signum: Signal number
            frame: Stack frame
        """
        logger.info(f"Received signal {signum}, shutting down")
        self._cleanup()
        sys.exit(0)
