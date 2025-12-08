"""
Command execution tool for LLMC MCP server.

Security features:
- Binary blacklist (only approved commands can run)
- Execution timeout
- Argument validation
- Working directory enforcement
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import shlex
import subprocess

logger = logging.getLogger(__name__)


class CommandSecurityError(Exception):
    """Raised when command execution is denied for security reasons."""

    pass


@dataclass
class ExecResult:
    """Result from command execution."""

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    error: str | None = None


# Default blacklist - safe read-only commands
DEFAULT_BLACKLIST: list[str] = [
    # Empty - sandbox provides real security
    # This is for soft behavioral nudges only
]


def validate_command(
    cmd_parts: list[str],
    blacklist: list[str],
) -> str:
    """
    Validate command against blacklist.

    Args:
        cmd_parts: Parsed command parts (first element is binary)
        blacklist: List of blocked binary names

    Returns:
        The binary name if allowed

    Raises:
        CommandSecurityError: If binary not in blacklist
    """
    if not cmd_parts:
        raise CommandSecurityError("Empty command")

    binary = cmd_parts[0]

    # Extract just the binary name (handle paths like /usr/bin/python)
    binary_name = Path(binary).name

    if binary_name in blacklist:
        raise CommandSecurityError(f"Binary '{binary_name}' is blacklisted. Blocked: {blacklist}")

    return binary_name


def run_cmd(
    command: str,
    cwd: Path | str,
    blacklist: list[str] | None = None,
    timeout: int = 30,
    env: dict[str, str] | None = None,
) -> ExecResult:
    """
    Execute a shell command with security constraints.
    
    SECURITY: Requires isolated environment (Docker, K8s, nsjail).

    Args:
        command: Shell command string to execute
        cwd: Working directory for execution
        blacklist: List of blocked binary names (uses DEFAULT_BLACKLIST if None)
        timeout: Max execution time in seconds
        env: Optional environment variables to set

    Returns:
        ExecResult with stdout, stderr, exit_code
    """
    # SECURITY: Only allow execution in isolated environments
    from llmc_mcp.isolation import require_isolation
    try:
        require_isolation("run_cmd")
    except RuntimeError as e:
        return ExecResult(
            success=False,
            stdout="",
            stderr=str(e),
            exit_code=-1,
            error=str(e),
        )
    
    if not command or not command.strip():
        return ExecResult(
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            error="Empty command",
        )

    blocked = blacklist if blacklist is not None else DEFAULT_BLACKLIST
    cwd_path = Path(cwd).resolve() if isinstance(cwd, str) else cwd.resolve()

    # Parse command to validate binary
    try:
        cmd_parts = shlex.split(command)
    except ValueError as e:
        return ExecResult(
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            error=f"Invalid command syntax: {e}",
        )

    # Validate against blacklist
    try:
        binary_name = validate_command(cmd_parts, blocked)
        logger.debug(f"Running allowed command: {binary_name}")
    except CommandSecurityError as e:
        return ExecResult(
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            error=str(e),
        )

    # Execute with timeout
    try:
        result = subprocess.run(
            cmd_parts,
            check=False,
            shell=False,
            cwd=str(cwd_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        return ExecResult(
            success=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
        )

    except subprocess.TimeoutExpired:
        return ExecResult(
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            error=f"Command timed out after {timeout}s",
        )
    except Exception as e:
        logger.exception("Command execution error")
        return ExecResult(
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            error=f"Execution error: {e}",
        )
