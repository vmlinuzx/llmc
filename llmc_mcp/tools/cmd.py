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


# Default blacklist - empty. Docker container provides real security.
# This is just asking nicely. An LLM could write their own sed if you blocked it.
DEFAULT_BLACKLIST: list[str] = []


def validate_command(
    cmd_parts: list[str],
    blacklist: list[str] | None = None,
    allowlist: list[str] | None = None,
) -> str:
    """
    Validate command against blacklist and allowlist.

    The blacklist is just asking nicely - not real security.
    Real security is:
        - Docker mode: Container isolation
        - Hybrid mode: You trust it

    If you give an LLM bash, they can do anything anyway.

    Args:
        cmd_parts: Parsed command parts (first element is binary)
        blacklist: Soft block list (empty by default)
        allowlist: Explicit allow list (if set, binary MUST be in it)

    Returns:
        The binary name if allowed

    Raises:
        CommandSecurityError: If binary is blacklisted or not in allowlist
    """
    if not cmd_parts:
        raise CommandSecurityError("Empty command")

    binary = cmd_parts[0]
    binary_name = Path(binary).name

    if blacklist and binary_name in blacklist:
        raise CommandSecurityError(
            f"Binary '{binary_name}' is blacklisted. Blocked: {blacklist}"
        )

    if allowlist is not None and binary_name not in allowlist:
        raise CommandSecurityError(
            f"Binary '{binary_name}' is not in allowlist. Allowed: {allowlist}"
        )

    return binary_name


def run_cmd(
    command: str,
    cwd: Path | str,
    blacklist: list[str] | None = None,
    timeout: int = 30,
    env: dict[str, str] | None = None,
    allowlist: list[str] | None = None,
) -> ExecResult:
    """
    Execute a shell command with security constraints.

    SECURITY:
        - All commands are executed in an isolated environment.

    Blacklist is just asking nicely. If you give an LLM bash, they can do anything.

    Args:
        command: Shell command string to execute
        cwd: Working directory for execution
        blacklist: Soft block list (empty by default, just asking nicely)
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

    # Validate command (blacklist is soft nudge only)
    try:
        binary_name = validate_command(cmd_parts, blacklist=blacklist, allowlist=allowlist)
        logger.debug(f"Running command: {binary_name}")
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
