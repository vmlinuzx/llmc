"""
Isolation Detection for LLMC MCP Server.

Dangerous tools (execute_code, run_cmd) should only run in isolated environments.
This module detects if we're running in a container/sandbox.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def is_isolated_environment() -> bool:
    """
    Detect if running in an isolated environment (container/sandbox).
    
    Checks for:
    1. Docker container (/.dockerenv file)
    2. Kubernetes pod (KUBERNETES_SERVICE_HOST env)
    3. Container runtime (cgroup containerd/docker markers)
    4. Explicit LLMC_ISOLATED=1 env var
    5. nsjail/firejail markers
    
    Returns:
        True if isolated, False if running on bare host.
    """
    # Explicit opt-in (for testing or known-safe environments)
    if os.environ.get("LLMC_ISOLATED", "").lower() in ("1", "true", "yes"):
        return True
    
    # Docker container
    if Path("/.dockerenv").exists():
        return True
    
    # Kubernetes
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return True
    
    # Container runtime detection via cgroup
    cgroup_path = Path("/proc/1/cgroup")
    if cgroup_path.exists():
        try:
            cgroup_content = cgroup_path.read_text()
            if any(marker in cgroup_content for marker in ("docker", "containerd", "lxc", "kubepods")):
                return True
        except (PermissionError, OSError):
            pass
    
    # Podman/systemd-nspawn detection
    container_env = os.environ.get("container")
    if container_env in ("docker", "podman", "systemd-nspawn", "lxc"):
        return True
    
    # nsjail detection (it sets specific env vars)
    if os.environ.get("NSJAIL"):
        return True
    
    # Firejail detection
    if os.environ.get("FIREJAIL"):
        return True
    
    return False


def require_isolation(tool_name: str) -> None:
    """
    Raise an error if not running in an isolated environment.
    
    Call this at the start of dangerous tool handlers.
    
    Args:
        tool_name: Name of the tool being invoked (for error message).
        
    Raises:
        RuntimeError: If not in an isolated environment.
    """
    if not is_isolated_environment():
        raise RuntimeError(
            f"SECURITY: Tool '{tool_name}' requires an isolated environment. "
            f"Run LLMC MCP server in Docker, Kubernetes, nsjail, or Firejail. "
            f"To bypass (DANGEROUS): set LLMC_ISOLATED=1"
        )


def isolation_status() -> dict:
    """Return current isolation status for debugging."""
    return {
        "isolated": is_isolated_environment(),
        "dockerenv_exists": Path("/.dockerenv").exists(),
        "kubernetes": bool(os.environ.get("KUBERNETES_SERVICE_HOST")),
        "container_env": os.environ.get("container"),
        "llmc_isolated_env": os.environ.get("LLMC_ISOLATED"),
    }
