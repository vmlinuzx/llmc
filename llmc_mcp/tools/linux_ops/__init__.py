"""
LLMC MCP LinuxOps Tools - Desktop Commander parity for Linux.

Phase L2: Process inspection & system snapshot.
Phase L3: Interactive processes / REPLs.
"""

from __future__ import annotations

from llmc_mcp.tools.linux_ops.proc import (
    mcp_linux_proc_kill,
    mcp_linux_proc_list,
    mcp_linux_proc_read,
    mcp_linux_proc_send,
    mcp_linux_proc_start,
    mcp_linux_proc_stop,
)
from llmc_mcp.tools.linux_ops.sysinfo import mcp_linux_sys_snapshot

__all__ = [
    # L2
    "mcp_linux_proc_list",
    "mcp_linux_proc_kill",
    "mcp_linux_sys_snapshot",
    # L3
    "mcp_linux_proc_start",
    "mcp_linux_proc_send",
    "mcp_linux_proc_read",
    "mcp_linux_proc_stop",
]
