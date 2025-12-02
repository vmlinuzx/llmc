"""
LinuxOps error types.

Custom exceptions with MCP-friendly error codes.
"""

from __future__ import annotations


class LinuxOpsError(Exception):
    """Base error for LinuxOps operations."""

    code: str = "LINUXOPS_ERROR"

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        if code is not None:
            self.code = code


class FeatureDisabledError(LinuxOpsError):
    """Feature is disabled in config."""

    code = "FEATURE_DISABLED"


class ProcessNotFoundError(LinuxOpsError):
    """Process with given PID does not exist."""

    code = "PROCESS_NOT_FOUND"


class PermissionDeniedError(LinuxOpsError):
    """Permission denied for operation."""

    code = "PERMISSION_DENIED"


class KillForbiddenError(LinuxOpsError):
    """Killing this process is forbidden (PID 1, self, etc)."""

    code = "KILL_FORBIDDEN"


class InvalidArgumentError(LinuxOpsError):
    """Invalid argument provided."""

    code = "INVALID_ARGUMENT"


class SystemInfoError(LinuxOpsError):
    """Failed to retrieve system information."""

    code = "SYSTEM_INFO_ERROR"



class ProcessLimitError(LinuxOpsError):
    """Process limit exceeded."""

    code = "PROC_LIMIT_EXCEEDED"


class ProcessStartError(LinuxOpsError):
    """Failed to start process."""

    code = "PROCESS_START_FAILED"
