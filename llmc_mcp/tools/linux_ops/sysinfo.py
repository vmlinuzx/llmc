"""
LinuxOps system information tools.

- sys_snapshot: CPU, memory, disk, load average snapshot
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llmc_mcp.tools.linux_ops.config import LinuxOpsConfig

from llmc_mcp.tools.linux_ops.errors import FeatureDisabledError
from llmc_mcp.tools.linux_ops.types import SysDiskInfo, SysSnapshot

logger = logging.getLogger(__name__)


def _get_snapshot_psutil() -> SysSnapshot:
    """Get system snapshot using psutil."""
    import psutil

    # CPU and load
    cpu_percent = psutil.cpu_percent(interval=0.1)  # Brief sample
    load1, load5, load15 = os.getloadavg()

    # Memory
    vm = psutil.virtual_memory()
    mem_used_mb = int(vm.used / (1024 * 1024))
    mem_total_mb = int(vm.total / (1024 * 1024))

    # Disks - filter to real partitions
    disks: list[SysDiskInfo] = []
    seen_mounts: set[str] = set()

    for part in psutil.disk_partitions(all=False):
        # Skip pseudo/virtual filesystems
        if part.fstype in ("squashfs", "tmpfs", "devtmpfs", "overlay"):
            continue
        if part.mountpoint in seen_mounts:
            continue
        seen_mounts.add(part.mountpoint)

        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append(
                SysDiskInfo(
                    mount=part.mountpoint,
                    used_percent=float(usage.percent),
                    total_gb=round(usage.total / (1024**3), 1),
                    free_gb=round(usage.free / (1024**3), 1),
                )
            )
        except (PermissionError, OSError):
            continue

    # Generate summary
    disk_summary = ""
    if disks:
        main_disk = disks[0]
        disk_summary = f", {main_disk.mount} {main_disk.used_percent:.0f}% used"

    short_summary = (
        f"CPU {cpu_percent:.0f}%, "
        f"Load {load1:.2f}/{load5:.2f}/{load15:.2f}, "
        f"RAM {mem_used_mb}/{mem_total_mb} MB"
        f"{disk_summary}"
    )

    return SysSnapshot(
        cpu_percent=cpu_percent,
        load_avg_1=load1,
        load_avg_5=load5,
        load_avg_15=load15,
        mem_used_mb=mem_used_mb,
        mem_total_mb=mem_total_mb,
        disks=disks,
        short_summary=short_summary,
    )


def _get_snapshot_shell() -> SysSnapshot:
    """Get system snapshot using shell commands (fallback)."""
    # Load average
    load1, load5, load15 = os.getloadavg()

    # CPU - parse /proc/stat or use top
    cpu_percent = 0.0
    try:
        # Quick approximation from /proc/stat
        with open("/proc/stat") as f:
            line = f.readline()
            parts = line.split()
            if parts[0] == "cpu":
                user, nice, system, idle = map(int, parts[1:5])
                total = user + nice + system + idle
                busy = user + nice + system
                cpu_percent = (busy / total) * 100 if total > 0 else 0.0
    except Exception:
        pass

    # Memory - parse /proc/meminfo
    mem_total_mb = 0
    mem_used_mb = 0
    try:
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    val = int(parts[1])  # kB
                    meminfo[key] = val

            mem_total_kb = meminfo.get("MemTotal", 0)
            mem_free_kb = meminfo.get("MemFree", 0)
            mem_buffers_kb = meminfo.get("Buffers", 0)
            mem_cached_kb = meminfo.get("Cached", 0)

            mem_total_mb = mem_total_kb // 1024
            mem_used_mb = (mem_total_kb - mem_free_kb - mem_buffers_kb - mem_cached_kb) // 1024
    except Exception:
        pass

    # Disks - parse df output
    disks: list[SysDiskInfo] = []
    try:
        result = subprocess.run(
            ["df", "-P", "-T"],  # POSIX output, with filesystem type
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) < 7:
                    continue
                fstype = parts[1]
                # Skip pseudo filesystems
                if fstype in ("tmpfs", "devtmpfs", "squashfs", "overlay"):
                    continue
                mount = parts[6]
                used_pct_str = parts[5].rstrip("%")
                try:
                    used_pct = float(used_pct_str)
                    total_kb = int(parts[2])
                    free_kb = int(parts[4])
                    disks.append(
                        SysDiskInfo(
                            mount=mount,
                            used_percent=used_pct,
                            total_gb=round(total_kb / (1024**2), 1),
                            free_gb=round(free_kb / (1024**2), 1),
                        )
                    )
                except ValueError:
                    continue
    except Exception:
        pass

    # Generate summary
    disk_summary = ""
    if disks:
        main_disk = disks[0]
        disk_summary = f", {main_disk.mount} {main_disk.used_percent:.0f}% used"

    short_summary = (
        f"CPU {cpu_percent:.0f}%, "
        f"Load {load1:.2f}/{load5:.2f}/{load15:.2f}, "
        f"RAM {mem_used_mb}/{mem_total_mb} MB"
        f"{disk_summary}"
    )

    return SysSnapshot(
        cpu_percent=cpu_percent,
        load_avg_1=load1,
        load_avg_5=load5,
        load_avg_15=load15,
        mem_used_mb=mem_used_mb,
        mem_total_mb=mem_total_mb,
        disks=disks,
        short_summary=short_summary,
    )


def mcp_linux_sys_snapshot(*, config: LinuxOpsConfig) -> dict:
    """
    Get a system resource snapshot.

    Returns:
        dict with CPU, memory, disk usage and summary
    """
    # Check feature flag
    if not config.features.system_enabled:
        raise FeatureDisabledError("System tools are disabled in config")

    # Try psutil first
    try:
        import psutil

        snapshot = _get_snapshot_psutil()
    except ImportError:
        logger.info("psutil not available, using shell fallback")
        snapshot = _get_snapshot_shell()
    except Exception as e:
        logger.warning(f"psutil failed, trying shell fallback: {e}")
        snapshot = _get_snapshot_shell()

    return snapshot.to_dict()
