"""
LinuxOps shared types.

Dataclasses for process info, system snapshots, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProcessInfo:
    """Information about a running process."""

    pid: int
    user: str
    cpu_percent: float
    mem_percent: float
    command: str

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "user": self.user,
            "cpu_percent": self.cpu_percent,
            "mem_percent": self.mem_percent,
            "command": self.command,
        }


@dataclass
class SysDiskInfo:
    """Disk usage information for a mount point."""

    mount: str
    used_percent: float
    total_gb: float = 0.0
    free_gb: float = 0.0

    def to_dict(self) -> dict:
        return {
            "mount": self.mount,
            "used_percent": self.used_percent,
            "total_gb": self.total_gb,
            "free_gb": self.free_gb,
        }


@dataclass
class SysSnapshot:
    """System resource snapshot."""

    cpu_percent: float
    load_avg_1: float
    load_avg_5: float
    load_avg_15: float
    mem_used_mb: int
    mem_total_mb: int
    disks: list[SysDiskInfo] = field(default_factory=list)
    short_summary: str = ""

    def to_dict(self) -> dict:
        return {
            "cpu_percent": self.cpu_percent,
            "load_avg": [self.load_avg_1, self.load_avg_5, self.load_avg_15],
            "mem_used_mb": self.mem_used_mb,
            "mem_total_mb": self.mem_total_mb,
            "disks": [d.to_dict() for d in self.disks],
            "short_summary": self.short_summary,
        }
