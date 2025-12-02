"""TE process wrapper and registry module."""

from llmc_mcp.te.process import (
    ManagedProcess,
    list_managed_processes,
    read_output,
    send_input,
    start_process,
    stop_process,
)

__all__ = [
    "ManagedProcess",
    "start_process",
    "send_input",
    "read_output",
    "stop_process",
    "list_managed_processes",
]
