"""
TE Process wrapper and registry.

Manages interactive processes (REPLs, shells) with:
- Start/stop lifecycle
- Non-blocking I/O
- In-memory registry
- Auto-cleanup of stale processes
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
import selectors
import shlex
import signal as sigmod
import subprocess
import time
import uuid

logger = logging.getLogger(__name__)

# Signal mapping
SIGNALS = {
    "TERM": sigmod.SIGTERM,
    "KILL": sigmod.SIGKILL,
    "INT": sigmod.SIGINT,
    "HUP": sigmod.SIGHUP,
}

# In-memory process registry
_REGISTRY: dict[str, ManagedProcess] = {}

# Default TTL for stale process cleanup (1 hour)
STALE_TTL_SEC = 3600


@dataclass
class ManagedProcess:
    """A managed interactive process."""

    proc_id: str
    pid: int
    command: str
    cwd: str
    start_time: float
    last_activity: float
    p: subprocess.Popen = field(repr=False)

    def is_running(self) -> bool:
        """Check if process is still running."""
        return self.p.poll() is None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict (without Popen)."""
        return {
            "proc_id": self.proc_id,
            "pid": self.pid,
            "command": self.command,
            "cwd": self.cwd,
            "start_time": self.start_time,
            "last_activity": self.last_activity,
            "running": self.is_running(),
        }


def _generate_proc_id() -> str:
    """Generate a unique process ID."""
    ts = int(time.time())
    rand = uuid.uuid4().hex[:8]
    return f"P_{ts}_{rand}"


def _cleanup_stale_processes(ttl_sec: float = STALE_TTL_SEC) -> int:
    """Remove stale processes from registry. Returns count removed."""
    now = time.time()
    to_remove = []

    for proc_id, mp in _REGISTRY.items():
        # Check if process exited
        if not mp.is_running():
            to_remove.append(proc_id)
            continue
        # Check if stale (no activity for TTL)
        if now - mp.last_activity > ttl_sec:
            logger.info(
                f"Cleaning up stale process {proc_id} (idle {now - mp.last_activity:.0f}s)"
            )
            try:
                mp.p.terminate()
                mp.p.wait(timeout=2)
            except Exception:
                try:
                    mp.p.kill()
                except Exception:
                    pass
            to_remove.append(proc_id)

    for proc_id in to_remove:
        _REGISTRY.pop(proc_id, None)

    return len(to_remove)


def start_process(
    command: str,
    cwd: str | None = None,
    env: dict | None = None,
) -> ManagedProcess:
    """
    Start a managed interactive process.

    Args:
        command: Shell command to run (e.g. "python -i", "bash")
        cwd: Working directory (defaults to current)
        env: Environment variable overrides

    Returns:
        ManagedProcess instance
    """
    # Cleanup stale processes opportunistically
    _cleanup_stale_processes()

    # Parse command
    argv = shlex.split(command)
    if not argv:
        raise ValueError("Empty command")

    # Resolve working directory
    if cwd:
        cwd = os.path.expanduser(cwd)
        if not os.path.isdir(cwd):
            raise ValueError(f"Working directory does not exist: {cwd}")
    else:
        cwd = os.getcwd()

    # Build environment
    proc_env = dict(os.environ)
    if env:
        proc_env.update(env)

    # Start process with pipes
    try:
        p = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=False,  # Binary mode for non-blocking I/O
            cwd=cwd,
            env=proc_env,
            bufsize=0,  # Unbuffered
        )
    except Exception as e:
        raise RuntimeError(f"Failed to start process: {e}") from None

    # Create managed process
    proc_id = _generate_proc_id()
    now = time.time()

    mp = ManagedProcess(
        proc_id=proc_id,
        pid=p.pid,
        command=command,
        cwd=cwd,
        start_time=now,
        last_activity=now,
        p=p,
    )

    _REGISTRY[proc_id] = mp
    logger.info(f"Started process {proc_id} (pid={p.pid}): {command}")

    return mp


def send_input(proc_id: str, data: str) -> None:
    """
    Send input to a managed process.

    Args:
        proc_id: Process ID from start_process
        data: Text to send (newline appended automatically)

    Raises:
        KeyError: If proc_id not found
        IOError: If write fails
    """
    mp = _REGISTRY.get(proc_id)
    if mp is None:
        raise KeyError(f"Process not found: {proc_id}")

    if not mp.is_running():
        raise OSError(f"Process {proc_id} has exited")

    # Append newline if not present
    if not data.endswith("\n"):
        data = data + "\n"

    try:
        mp.p.stdin.write(data.encode("utf-8"))
        mp.p.stdin.flush()
        mp.last_activity = time.time()
    except Exception as e:
        raise OSError(f"Failed to write to process {proc_id}: {e}") from None


def read_output(proc_id: str, timeout_sec: float = 1.0) -> tuple[str, str]:
    """
    Read available output from a managed process.

    Uses selectors.DefaultSelector (epoll on Linux, kqueue on BSD/macOS)
    for scalable non-blocking I/O. Unlike select.select(), this:
    - Scales O(1) instead of O(N) for fd count
    - Not limited to FD_SETSIZE (typically 1024)

    Args:
        proc_id: Process ID
        timeout_sec: Max time to wait for output

    Returns:
        Tuple of (output_text, state) where state is one of:
        - "running": Process still active
        - "exited": Process has terminated
        - "no_such_process": proc_id not in registry
    """
    mp = _REGISTRY.get(proc_id)
    if mp is None:
        return ("", "no_such_process")

    output_parts = []
    deadline = time.time() + timeout_sec

    # Use selectors for scalable I/O (epoll on Linux)
    sel = selectors.DefaultSelector()
    stdout_fd = mp.p.stdout.fileno()
    
    try:
        sel.register(stdout_fd, selectors.EVENT_READ)
        
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                break

            # Check if data available (epoll/kqueue under the hood)
            events = sel.select(timeout=min(remaining, 0.1))

            if events:
                try:
                    # Read available data (non-blocking) via os.read
                    # This avoids the blocking behavior of file.read()
                    chunk = os.read(stdout_fd, 4096)
                    if chunk:
                        output_parts.append(chunk)
                        mp.last_activity = time.time()
                    else:
                        # EOF - process likely exited
                        break
                except Exception:
                    break
            else:
                # No data available, check if we should keep waiting
                # If process exited, stop waiting
                if not mp.is_running():
                    break
    finally:
        sel.unregister(stdout_fd)
        sel.close()

    # Decode captured bytes
    output_bytes = b"".join(output_parts)
    output = output_bytes.decode("utf-8", errors="replace")

    # Determine state
    if mp.is_running():
        state = "running"
    else:
        state = "exited"

    return (output, state)


def stop_process(proc_id: str, signal_name: str = "TERM") -> bool:
    """
    Stop a managed process.

    Args:
        proc_id: Process ID
        signal_name: Signal to send (TERM, KILL, INT, HUP)

    Returns:
        True if process was stopped, False if not found
    """
    mp = _REGISTRY.get(proc_id)
    if mp is None:
        return False

    sig = SIGNALS.get(signal_name.upper(), sigmod.SIGTERM)

    try:
        if mp.is_running():
            mp.p.send_signal(sig)
            # Give it a moment to exit gracefully
            try:
                mp.p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # Force kill if still running
                if mp.is_running():
                    mp.p.kill()
                    mp.p.wait(timeout=1)

        logger.info(f"Stopped process {proc_id} (signal={signal_name})")
    except Exception as e:
        logger.warning(f"Error stopping process {proc_id}: {e}")

    # Remove from registry
    _REGISTRY.pop(proc_id, None)
    return True


def list_managed_processes() -> list[ManagedProcess]:
    """
    List all managed processes.

    Returns:
        List of ManagedProcess instances
    """
    # Cleanup stale first
    _cleanup_stale_processes()
    return list(_REGISTRY.values())


def get_process(proc_id: str) -> ManagedProcess | None:
    """Get a managed process by ID."""
    return _REGISTRY.get(proc_id)


def count_processes() -> int:
    """Get count of active managed processes."""
    return len(_REGISTRY)
