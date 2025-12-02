"""
LinuxOps process tools.

- proc_list: List running processes with resource usage
- proc_kill: Send signals to processes with safety guards
"""

from __future__ import annotations

import getpass
import logging
import os
import signal as sigmod
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llmc_mcp.tools.linux_ops.config import LinuxOpsConfig

from llmc_mcp.tools.linux_ops.errors import (
    FeatureDisabledError,
    InvalidArgumentError,
    KillForbiddenError,
    PermissionDeniedError,
    ProcessLimitError,
    ProcessNotFoundError,
    ProcessStartError,
)
from llmc_mcp.tools.linux_ops.types import ProcessInfo

logger = logging.getLogger(__name__)

# Signal name to signal number mapping
SIGNALS = {
    "TERM": sigmod.SIGTERM,
    "KILL": sigmod.SIGKILL,
    "INT": sigmod.SIGINT,
    "HUP": sigmod.SIGHUP,
    "STOP": sigmod.SIGSTOP,
    "CONT": sigmod.SIGCONT,
}

# MCP server PID (cached at module load)
MCP_PID = os.getpid()


def _list_processes_psutil(user_filter: str | None = None) -> list[ProcessInfo]:
    """List processes using psutil (preferred method)."""
    import psutil

    infos: list[ProcessInfo] = []
    for p in psutil.process_iter(
        attrs=["pid", "username", "cpu_percent", "memory_percent", "cmdline", "name"]
    ):
        try:
            pinfo = p.info
            username = pinfo.get("username") or ""

            # Apply user filter
            if user_filter is not None and username != user_filter:
                continue

            # Build command string
            cmdline = pinfo.get("cmdline")
            if cmdline:
                command = " ".join(cmdline)
            else:
                command = pinfo.get("name") or ""

            infos.append(
                ProcessInfo(
                    pid=pinfo["pid"],
                    user=username,
                    cpu_percent=float(pinfo.get("cpu_percent") or 0.0),
                    mem_percent=float(pinfo.get("memory_percent") or 0.0),
                    command=command[:500],  # Truncate long commands
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return infos


def _list_processes_shell(user_filter: str | None = None) -> list[ProcessInfo]:
    """List processes using ps command (fallback method)."""
    # ps output: PID USER %CPU %MEM COMMAND
    cmd = ["ps", "-eo", "pid,user,%cpu,%mem,command", "--sort=-%cpu"]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        
        if result.returncode != 0:
            logger.warning(f"ps command failed: {result.stderr}")
            return []
        
        infos: list[ProcessInfo] = []
        lines = result.stdout.strip().split("\n")
        
        # Skip header
        for line in lines[1:]:
            parts = line.split(None, 4)  # Split into 5 parts max
            if len(parts) < 5:
                continue
            
            try:
                pid = int(parts[0])
                user = parts[1]
                cpu = float(parts[2])
                mem = float(parts[3])
                command = parts[4][:500]
                
                if user_filter is not None and user != user_filter:
                    continue
                
                infos.append(ProcessInfo(
                    pid=pid,
                    user=user,
                    cpu_percent=cpu,
                    mem_percent=mem,
                    command=command,
                ))
            except (ValueError, IndexError):
                continue
        
        return infos
        
    except subprocess.TimeoutExpired:
        logger.error("ps command timed out")
        return []
    except Exception as e:
        logger.error(f"Failed to run ps: {e}")
        return []


def _get_process_owner(pid: int) -> str | None:
    """Get the username that owns a process."""
    try:
        import psutil
        p = psutil.Process(pid)
        return p.username()
    except Exception:
        # Fallback to /proc
        try:
            stat_path = f"/proc/{pid}/status"
            with open(stat_path) as f:
                for line in f:
                    if line.startswith("Uid:"):
                        uid = int(line.split()[1])
                        import pwd
                        return pwd.getpwuid(uid).pw_name
        except Exception:
            pass
    return None


def mcp_linux_proc_list(
    *,
    config: LinuxOpsConfig,
    max_results: int = 200,
    user: str | None = None,
) -> dict:
    """
    List running processes with resource usage.
    
    Args:
        config: LinuxOps configuration
        max_results: Maximum processes to return (1-5000)
        user: Optional username filter
        
    Returns:
        dict with processes list, total count, truncated flag
    """
    # Check feature flag
    if not config.features.proc_enabled:
        raise FeatureDisabledError("Process tools are disabled in config")
    
    # Clamp max_results
    max_results = max(1, min(max_results, 5000))
    
    # Try psutil first, fall back to shell
    try:
        import psutil
        processes = _list_processes_psutil(user)
    except ImportError:
        logger.info("psutil not available, using shell fallback")
        processes = _list_processes_shell(user)
    
    # Sort by CPU descending
    processes.sort(key=lambda p: p.cpu_percent, reverse=True)
    
    total = len(processes)
    truncated = total > max_results
    
    if truncated:
        processes = processes[:max_results]
    
    return {
        "processes": [p.to_dict() for p in processes],
        "total_processes": total,
        "truncated": truncated,
    }


def mcp_linux_proc_kill(
    *,
    config: LinuxOpsConfig,
    pid: int,
    signal: str = "TERM",
) -> dict:
    """
    Send a signal to a process.
    
    Args:
        config: LinuxOps configuration
        pid: Process ID to signal
        signal: Signal name (TERM, KILL, INT, HUP, STOP, CONT)
        
    Returns:
        dict with success status and message
        
    Raises:
        FeatureDisabledError: If proc tools disabled
        KillForbiddenError: If trying to kill PID 1 or MCP server
        PermissionDeniedError: If not allowed to kill other users' processes
        InvalidArgumentError: If invalid signal name
        ProcessNotFoundError: If process doesn't exist
    """
    # Check feature flag
    if not config.features.proc_enabled:
        raise FeatureDisabledError("Process tools are disabled in config")
    
    # Validate signal
    signal = signal.upper()
    if signal not in SIGNALS:
        raise InvalidArgumentError(
            f"Invalid signal '{signal}'. Valid signals: {', '.join(SIGNALS.keys())}"
        )
    
    # Safety checks
    if pid == 1:
        raise KillForbiddenError("Cannot kill PID 1 (init/systemd)")
    
    if pid == MCP_PID:
        raise KillForbiddenError("Cannot kill MCP server process")
    
    if pid <= 0:
        raise InvalidArgumentError(f"Invalid PID: {pid}")
    
    # Check process exists
    try:
        os.kill(pid, 0)  # Signal 0 just checks existence
    except ProcessLookupError:
        raise ProcessNotFoundError(f"Process {pid} not found")
    except PermissionError:
        # Process exists but we can't signal it
        pass
    
    # Check ownership if configured
    if not config.process_limits.allow_kill_other_users:
        current_user = getpass.getuser()
        proc_owner = _get_process_owner(pid)
        
        if proc_owner and proc_owner != current_user:
            raise PermissionDeniedError(
                f"Cannot kill process {pid} owned by '{proc_owner}' "
                f"(current user: '{current_user}'). "
                f"Set allow_kill_other_users=true to override."
            )
    
    # Send the signal
    try:
        os.kill(pid, SIGNALS[signal])
        logger.info(f"Sent SIG{signal} to pid {pid}")
        return {
            "success": True,
            "message": f"Sent SIG{signal} to pid {pid}",
        }
    except ProcessLookupError:
        raise ProcessNotFoundError(f"Process {pid} no longer exists")
    except PermissionError as e:
        raise PermissionDeniedError(f"Permission denied killing pid {pid}: {e}")
    except Exception as e:
        logger.error(f"Failed to kill pid {pid}: {e}")
        return {
            "success": False,
            "message": f"Failed to send SIG{signal} to pid {pid}: {e}",
        }



# ============================================================================
# L3: Interactive Process / REPL Tools
# ============================================================================

def mcp_linux_proc_start(
    command: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    initial_read_timeout_ms: int = 1000,
    *,
    config: LinuxOpsConfig,
) -> dict:
    """
    Start a managed interactive process (REPL).

    Args:
        command: Shell command to run (e.g. "python -i", "bash")
        cwd: Optional working directory
        env: Optional environment overrides
        initial_read_timeout_ms: Time to wait for initial output
        config: LinuxOps configuration

    Returns:
        dict with proc_id, pid, first_output, state
    """
    from llmc_mcp.te.process import start_process, read_output, count_processes

    # Check feature flag
    if not config.features.repl_enabled:
        raise FeatureDisabledError("REPL tools are disabled in config")

    # Check process limits
    current_count = count_processes()
    if current_count >= config.process_limits.max_procs_total:
        raise ProcessLimitError(
            f"Process limit reached ({current_count}/{config.process_limits.max_procs_total})"
        )

    # Start the process
    try:
        mp = start_process(command=command, cwd=cwd, env=env)
    except ValueError as e:
        raise InvalidArgumentError(str(e))
    except RuntimeError as e:
        raise ProcessStartError(str(e))

    # Read initial output
    timeout_sec = initial_read_timeout_ms / 1000.0
    first_output, state = read_output(mp.proc_id, timeout_sec=timeout_sec)

    return {
        "proc_id": mp.proc_id,
        "pid": mp.pid,
        "first_output": first_output,
        "state": state,
    }


def mcp_linux_proc_send(
    proc_id: str,
    input: str,
    *,
    config: LinuxOpsConfig,
) -> dict:
    """
    Send input to a managed process.

    Args:
        proc_id: Process ID from proc_start
        input: Text to send (newline appended automatically)
        config: LinuxOps configuration

    Returns:
        dict with acknowledged flag
    """
    from llmc_mcp.te.process import send_input

    if not config.features.repl_enabled:
        raise FeatureDisabledError("REPL tools are disabled in config")

    try:
        send_input(proc_id, input)
        return {"acknowledged": True}
    except KeyError:
        raise ProcessNotFoundError(f"Process not found: {proc_id}")
    except IOError as e:
        return {"acknowledged": False, "error": str(e)}


def mcp_linux_proc_read(
    proc_id: str,
    timeout_ms: int = 1000,
    *,
    config: LinuxOpsConfig,
) -> dict:
    """
    Read output from a managed process.

    Args:
        proc_id: Process ID
        timeout_ms: Max time to wait (0-10000)
        config: LinuxOps configuration

    Returns:
        dict with output and state
    """
    from llmc_mcp.te.process import read_output

    if not config.features.repl_enabled:
        raise FeatureDisabledError("REPL tools are disabled in config")

    timeout_sec = max(0, min(timeout_ms, 10000)) / 1000.0
    output, state = read_output(proc_id, timeout_sec=timeout_sec)

    return {"output": output, "state": state}


def mcp_linux_proc_stop(
    proc_id: str,
    signal: str = "TERM",
    *,
    config: LinuxOpsConfig,
) -> dict:
    """
    Stop a managed process.

    Args:
        proc_id: Process ID
        signal: Signal to send (TERM, KILL, INT, HUP)
        config: LinuxOps configuration

    Returns:
        dict with success and message
    """
    from llmc_mcp.te.process import stop_process

    if not config.features.repl_enabled:
        raise FeatureDisabledError("REPL tools are disabled in config")

    success = stop_process(proc_id, signal_name=signal)

    if success:
        return {"success": True, "message": f"Stopped process {proc_id} (signal={signal})"}
    else:
        return {"success": False, "message": f"Process not found: {proc_id}"}
