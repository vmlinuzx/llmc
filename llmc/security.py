"""
Shared security utilities for LLMC.

This module provides path validation and security primitives used across
the codebase to prevent path traversal attacks and other security issues.
"""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse


def validate_ollama_url(url: str):
    """
    Validates that the provided URL for Ollama is safe to connect to.

    This function checks for:
    - A valid URL format (http or https).
    - The hostname resolves to a public IP address (localhost is allowed).
    - The IP address is not a loopback (other than localhost), private, or reserved IP.

    Args:
        url: The URL string to validate.

    Raises:
        ValueError: If the URL is malformed, the hostname cannot be resolved,
                    or the IP address is not a public IP.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Invalid URL scheme. Only http and https are allowed.")

        hostname = parsed.hostname
        if not hostname:
            raise ValueError("URL is missing a hostname.")

        # Allow localhost explicitly as it's a common use case for local dev
        if hostname == "localhost":
            return

        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)

        if ip.is_loopback or ip.is_private or ip.is_reserved:
            raise ValueError(
                f"Hostname '{hostname}' resolves to the non-public IP address {ip}. "
                "For security reasons, only connections to public IPs or "
                "'localhost' are permitted."
            )

    except socket.gaierror:
        raise ValueError(f"Could not resolve hostname: {hostname}") from None
    except ValueError as e:
        # Re-raise our own ValueErrors
        raise e
    except Exception as e:
        # Catch any other parsing/validation errors
        raise ValueError(f"URL validation failed: {e}") from e


class PathSecurityError(ValueError):
    """Raised when path access is denied for security reasons."""

    pass


def normalize_path(repo_root: Path, target: str) -> Path:
    """Resolve target path relative to repo root, with fuzzy suffix matching.

    Security: Rejects paths outside repo_root to prevent path traversal attacks.

    Args:
        repo_root: The repository root directory (security boundary).
        target: The target path string (can be relative, absolute, or a suffix).

    Returns:
        Path relative to repo_root.

    Raises:
        PathSecurityError: If path is outside repo_root boundary or contains
            security-relevant characters (null bytes, etc.).

    Example:
        >>> normalize_path(Path("/repo"), "src/main.py")
        PosixPath('src/main.py')

        >>> normalize_path(Path("/repo"), "/repo/src/main.py")
        PosixPath('src/main.py')

        >>> normalize_path(Path("/repo"), "../../../etc/passwd")
        PathSecurityError: Path '../../../etc/passwd' escapes repository boundary...
    """
    # Security: Reject null bytes
    if "\x00" in target:
        raise PathSecurityError("Path contains null bytes")

    # 1. Try as exact path (relative or absolute)
    p = Path(target)
    if p.is_absolute():
        # Security: Absolute paths MUST be inside repo_root
        resolved = p.resolve()
        try:
            return resolved.relative_to(repo_root.resolve())
        except ValueError:
            raise PathSecurityError(
                f"Path '{target}' is outside repository boundary. "
                f"Only paths within {repo_root} are allowed."
            )

    # Security: Check for traversal attempts (../)
    full_path = (repo_root / target).resolve()
    try:
        relative_path = full_path.relative_to(repo_root.resolve())
    except ValueError:
        raise PathSecurityError(
            f"Path '{target}' escapes repository boundary via traversal. "
            f"Only paths within {repo_root} are allowed."
        )

    if full_path.exists():
        return relative_path

    # 2. Fuzzy Suffix Match
    # Find files in repo that end with the target string
    # This is a simple heuristic: find 'router.py' -> 'scripts/router.py'
    matches = []
    target_name = p.name

    # Walk repo (skip hidden/venv)
    for file in repo_root.rglob(f"*{target_name}"):
        if any(
            part.startswith(".") or part in ("venv", "__pycache__", "node_modules")
            for part in file.parts
        ):
            continue

        if str(file).endswith(target):
            try:
                matches.append(file.relative_to(repo_root))
            except ValueError:
                pass

    if not matches:
        return p  # Return original to fail downstream or be handled as symbol

    # Sort matches: shortest path length first, then alphabetical
    matches.sort(key=lambda m: (len(m.parts), str(m)))

    return matches[0]
