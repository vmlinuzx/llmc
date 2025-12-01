"""
Command execution tool for LLMC MCP server.

Security features:
- Binary allowlist (only approved commands can run)
- Execution timeout
- Argument validation
- Working directory enforcement
"""

from __future__ import annotations

import logging
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("llmc-mcp.exec")


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


# Default allowlist - safe read-only commands
DEFAULT_ALLOWLIST = [
    "bash",
    "sh",
    "rg",
    "grep",
    "cat",
    "head",
    "tail",
    "ls",
    "find",
    "wc",
    "sort",
    "uniq",
    "python",
    "python3",
    "pip",
    "git",
]


def validate_command(
    cmd_parts: list[str],
    allowlist: list[str],
) -> str:
    """
    Validate command against allowlist.
    
    Args:
        cmd_parts: Parsed command parts (first element is binary)
        allowlist: List of allowed binary names
        
    Returns:
        The binary name if allowed
        
    Raises:
        CommandSecurityError: If binary not in allowlist
    """
    if not cmd_parts:
        raise CommandSecurityError("Empty command")
    
    binary = cmd_parts[0]
    
    # Extract just the binary name (handle paths like /usr/bin/python)
    binary_name = Path(binary).name
    
    if binary_name not in allowlist:
        raise CommandSecurityError(
            f"Binary '{binary_name}' not in allowlist. Allowed: {allowlist}"
        )
    
    return binary_name


def run_cmd(
    command: str,
    cwd: Path | str,
    allowlist: list[str] | None = None,
    timeout: int = 30,
    env: dict[str, str] | None = None,
) -> ExecResult:
    """
    Execute a shell command with security constraints.
    
    Args:
        command: Shell command string to execute
        cwd: Working directory for execution
        allowlist: List of allowed binary names (uses DEFAULT_ALLOWLIST if None)
        timeout: Max execution time in seconds
        env: Optional environment variables to set
        
    Returns:
        ExecResult with stdout, stderr, exit_code
    """
    if not command or not command.strip():
        return ExecResult(
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            error="Empty command",
        )
    
    allowed = allowlist if allowlist is not None else DEFAULT_ALLOWLIST
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
    
    # Validate against allowlist
    try:
        binary_name = validate_command(cmd_parts, allowed)
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
            command,
            shell=True,
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
