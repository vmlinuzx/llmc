"""
Isolation Detection for LLMC MCP Server.

Dangerous tools (execute_code, run_cmd) should only run in isolated environments.
This module detects if we're running in a container/sandbox.
"""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import re


@lru_cache(maxsize=1)
def is_isolated_environment() -> bool:
    """
    Detect if running in an isolated environment (container/sandbox).

    Checks for:
    1. Docker container (/.dockerenv file)
    2. Podman/OCI container (/run/.containerenv file)
    3. Kubernetes pod (KUBERNETES_SERVICE_HOST env)
    4. Container runtime (cgroup containerd/docker markers)
    5. Explicit LLMC_ISOLATED=1 env var
    6. nsjail/firejail markers

    Returns:
        True if isolated, False if running on bare host.
    """
    # Explicit opt-in (for testing or known-safe environments)
    if os.environ.get("LLMC_ISOLATED", "").lower() in ("1", "true", "yes"):
        return True

    # Docker container
    if Path("/.dockerenv").exists():
        return True

    # Podman and other OCI runtimes
    if Path("/run/.containerenv").exists():
        return True

    # Kubernetes
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return True

    # Container runtime detection via cgroup
    cgroup_path = Path("/proc/1/cgroup")
    if cgroup_path.exists():
        try:
            cgroup_content = cgroup_path.read_text()
            # This regex uses positive matching for known container cgroup path
            # structures, which is more robust than blacklisting.
            # - `:/docker/`: Standard Docker with cgroupfs driver.
            # - `:/kubepods/`: Standard Kubernetes pod cgroup.
            # - `docker-.*\.scope`: Standard Docker with systemd cgroup driver.
            # - `:/lxc/`: Standard LXC container.
            # - `:/containerd/`: Standard containerd path.
            # This is specific enough to avoid false positives from host services
            # like 'docker.service'.
            container_patterns = [
                r":/docker/",
                r":/kubepods/",
                r"docker-.*\.scope",
                r":/lxc/",
                r":/containerd/",
            ]
            if any(re.search(p, cgroup_content) for p in container_patterns):
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
        "podman_containerenv_exists": Path("/run/.containerenv").exists(),
        "kubernetes": bool(os.environ.get("KUBERNETES_SERVICE_HOST")),
        "container_env": os.environ.get("container"),
        "llmc_isolated_env": os.environ.get("LLMC_ISOLATED"),
    }
