"""
Filesystem tools for LLMC MCP server.

Security features:
- Path normalization (resolves .., symlinks)
- Traversal protection (must stay within allowed_roots)
- Device file rejection
- Symlink escape detection
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
import stat as stat_module
from typing import Any

# Human-readable formatting (optional - graceful fallback)
try:
    import humanize
    HUMANIZE_AVAILABLE = True
except ImportError:
    HUMANIZE_AVAILABLE = False


def _human_size(size_bytes: int) -> str:
    """Return human-readable file size."""
    if HUMANIZE_AVAILABLE:
        return humanize.naturalsize(size_bytes, binary=True)
    # Fallback
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def _human_time(dt: datetime) -> str:
    """Return human-readable relative time."""
    if HUMANIZE_AVAILABLE:
        return humanize.naturaltime(dt)
    # Fallback
    return dt.isoformat()


class PathSecurityError(Exception):
    """Raised when path access is denied for security reasons."""

    pass


@dataclass
class FsResult:
    """Result from filesystem operation."""

    success: bool
    data: Any
    meta: dict[str, Any]
    error: str | None = None


def normalize_path(path: str | Path) -> Path:
    """
    Normalize and resolve a path safely.

    - Expands ~ to home directory
    - Resolves .. and symlinks
    - Returns absolute path

    Raises:
        PathSecurityError: If path contains null bytes or is otherwise invalid
    """
    path_str = str(path)

    # Reject null bytes (potential injection)
    if "\x00" in path_str:
        raise PathSecurityError("Path contains null bytes")

    # Expand ~ and make absolute
    expanded = os.path.expanduser(path_str)
    resolved = Path(expanded).resolve()

    return resolved


def check_path_allowed(path: Path, allowed_roots: list[str]) -> bool:
    """
    Check if path is within allowed roots.

    Args:
        path: Resolved absolute path to check
        allowed_roots: List of allowed root directories

    Returns:
        True if path is within an allowed root

    Note:
        Empty allowed_roots means full access (per SDD)
    """
    # Empty list = full access (operator choice)
    if not allowed_roots:
        return True

    # Resolve all roots for comparison
    resolved_roots = [Path(r).resolve() for r in allowed_roots]

    # Check if path is under any allowed root
    for root in resolved_roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue

    return False


def _is_device_file(path: Path) -> bool:
    """Check if path is a device file (block/char special)."""
    try:
        mode = path.stat().st_mode
        return stat_module.S_ISBLK(mode) or stat_module.S_ISCHR(mode)
    except OSError:
        return False


def _check_symlink_escape(path: Path, allowed_roots: list[str]) -> bool:
    """
    Check if a symlink resolves outside allowed roots.

    Returns True if the symlink escapes (i.e., is NOT allowed).
    """
    if not path.is_symlink():
        return False

    # Where does symlink actually point?
    resolved = path.resolve()
    return not check_path_allowed(resolved, allowed_roots)


def validate_path(path: str | Path, allowed_roots: list[str]) -> Path:
    """
    Validate and normalize path for safe access.

    Args:
        path: Raw path from user
        allowed_roots: Allowed root directories

    Returns:
        Validated, resolved Path

    Raises:
        PathSecurityError: If path is not safe to access
    """
    resolved = normalize_path(path)

    # Check allowed roots
    if not check_path_allowed(resolved, allowed_roots):
        raise PathSecurityError(f"Path {resolved} is outside allowed roots: {allowed_roots}")

    # Check for device files
    if resolved.exists() and _is_device_file(resolved):
        raise PathSecurityError(f"Cannot access device file: {resolved}")

    # Check symlink escape
    if _check_symlink_escape(resolved, allowed_roots):
        raise PathSecurityError(f"Symlink escapes allowed roots: {resolved}")

    return resolved


def read_file(
    path: str | Path,
    allowed_roots: list[str],
    max_bytes: int = 1_048_576,  # 1MB default
    encoding: str = "utf-8",
) -> FsResult:
    """
    Read file contents safely.

    Args:
        path: File path to read
        allowed_roots: Allowed root directories
        max_bytes: Maximum bytes to read (truncates if exceeded)
        encoding: Text encoding (tries binary fallback)

    Returns:
        FsResult with file contents or error
    """
    try:
        resolved = validate_path(path, allowed_roots)

        if not resolved.exists():
            return FsResult(
                success=False,
                data=None,
                meta={"path": str(resolved)},
                error=f"File not found: {resolved}",
            )

        if resolved.is_fifo():
            return FsResult(
                success=False,
                data=None,
                meta={"path": str(resolved)},
                error=f"Cannot read from a FIFO: {resolved}",
            )

        if not resolved.is_file():
            return FsResult(
                success=False,
                data=None,
                meta={"path": str(resolved)},
                error=f"Not a file: {resolved}",
            )

        # Get file size
        file_size = resolved.stat().st_size
        truncated = file_size > max_bytes

        # Read file
        try:
            with open(resolved, encoding=encoding) as f:
                content = f.read(max_bytes)
        except UnicodeDecodeError:
            # Fall back to binary read
            with open(resolved, "rb") as f:
                raw = f.read(max_bytes)
                content = raw.decode("utf-8", errors="replace")

        return FsResult(
            success=True,
            data=content,
            meta={
                "path": str(resolved),
                "size": file_size,
                "size_human": _human_size(file_size),
                "truncated": truncated,
                "encoding": encoding,
            },
        )

    except PathSecurityError as e:
        return FsResult(
            success=False,
            data=None,
            meta={"path": str(path)},
            error=str(e),
        )
    except Exception as e:
        return FsResult(
            success=False,
            data=None,
            meta={"path": str(path)},
            error=f"Read error: {e}",
        )


def list_dir(
    path: str | Path,
    allowed_roots: list[str],
    max_entries: int = 1000,
    include_hidden: bool = False,
) -> FsResult:
    """
    List directory contents safely.

    Args:
        path: Directory path to list
        allowed_roots: Allowed root directories
        max_entries: Maximum entries to return
        include_hidden: Include hidden files (starting with .)

    Returns:
        FsResult with list of entries or error
    """
    try:
        resolved = validate_path(path, allowed_roots)

        if not resolved.exists():
            return FsResult(
                success=False,
                data=None,
                meta={"path": str(resolved)},
                error=f"Directory not found: {resolved}",
            )

        if not resolved.is_dir():
            return FsResult(
                success=False,
                data=None,
                meta={"path": str(resolved)},
                error=f"Not a directory: {resolved}",
            )

        entries: list[dict[str, Any]] = []

        total_count = 0

        for entry in sorted(resolved.iterdir()):
            total_count += 1

            # Skip hidden unless requested
            if not include_hidden and entry.name.startswith("."):
                continue

            if len(entries) >= max_entries:
                continue  # Count but don't add

            entry_type = "dir" if entry.is_dir() else "file"
            if entry.is_symlink():
                entry_type = "symlink"

            # Get size for files
            try:
                entry_stat = entry.stat()
                size = entry_stat.st_size if entry_type == "file" else None
                mtime = datetime.fromtimestamp(entry_stat.st_mtime, tz=UTC)
            except OSError:
                size = None
                mtime = None

            entry_data = {
                "name": entry.name,
                "type": entry_type,
                "path": str(entry),
            }
            if size is not None:
                entry_data["size"] = size
                entry_data["size_human"] = _human_size(size)
            if mtime is not None:
                entry_data["modified"] = _human_time(mtime)

            entries.append(entry_data)

        return FsResult(
            success=True,
            data=entries,
            meta={
                "path": str(resolved),
                "total_entries": total_count,
                "returned_entries": len(entries),
                "truncated": total_count > max_entries,
            },
        )

    except PathSecurityError as e:
        return FsResult(
            success=False,
            data=None,
            meta={"path": str(path)},
            error=str(e),
        )
    except PermissionError:
        return FsResult(
            success=False,
            data=None,
            meta={"path": str(path)},
            error=f"Permission denied: {path}",
        )
    except Exception as e:
        return FsResult(
            success=False,
            data=None,
            meta={"path": str(path)},
            error=f"List error: {e}",
        )


def stat_path(
    path: str | Path,
    allowed_roots: list[str],
) -> FsResult:
    """
    Get file/directory metadata safely.

    Args:
        path: Path to stat
        allowed_roots: Allowed root directories

    Returns:
        FsResult with stat info or error
    """
    try:
        resolved = validate_path(path, allowed_roots)

        if not resolved.exists():
            return FsResult(
                success=False,
                data=None,
                meta={"path": str(resolved)},
                error=f"Path not found: {resolved}",
            )

        st = resolved.stat()

        # Determine type
        if resolved.is_symlink():
            file_type = "symlink"
        elif resolved.is_dir():
            file_type = "directory"
        elif resolved.is_file():
            file_type = "file"
        else:
            file_type = "other"

        # Format timestamps as ISO UTC
        mtime = datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat()
        ctime = datetime.fromtimestamp(st.st_ctime, tz=UTC).isoformat()
        atime = datetime.fromtimestamp(st.st_atime, tz=UTC).isoformat()

        # Create datetime objects for human-readable output
        mtime_dt = datetime.fromtimestamp(st.st_mtime, tz=UTC)
        datetime.fromtimestamp(st.st_ctime, tz=UTC)
        datetime.fromtimestamp(st.st_atime, tz=UTC)

        return FsResult(
            success=True,
            data={
                "size": st.st_size,
                "size_human": _human_size(st.st_size),
                "type": file_type,
                "mode": oct(st.st_mode)[-4:],  # e.g., "0644"
                "mtime": mtime,
                "mtime_human": _human_time(mtime_dt),
                "ctime": ctime,
                "atime": atime,
                "uid": st.st_uid,
                "gid": st.st_gid,
                "nlink": st.st_nlink,
            },
            meta={"path": str(resolved)},
        )

    except PathSecurityError as e:
        return FsResult(
            success=False,
            data=None,
            meta={"path": str(path)},
            error=str(e),
        )
    except Exception as e:
        return FsResult(
            success=False,
            data=None,
            meta={"path": str(path)},
            error=f"Stat error: {e}",
        )


# ============================================================================
# Write Operations (L1 Phase 2)
# ============================================================================

import hashlib
import shutil


def write_file(
    path: str | Path,
    allowed_roots: list[str],
    content: str,
    mode: str = "rewrite",
    expected_sha256: str | None = None,
    max_bytes: int = 10_485_760,  # 10MB default limit
) -> FsResult:
    """
    Write or append content to a file.

    Args:
        path: File path to write
        allowed_roots: Allowed root directories
        content: Text content to write
        mode: "rewrite" (overwrite) or "append"
        expected_sha256: If provided, verify existing file hash before write
        max_bytes: Maximum bytes allowed to write

    Returns:
        FsResult with bytes_written and new_sha256
    """
    try:
        resolved = validate_path(path, allowed_roots)
        content_bytes = content.encode("utf-8")

        if len(content_bytes) > max_bytes:
            return FsResult(
                success=False,
                data=None,
                meta={"path": str(resolved)},
                error=f"Content too large: {len(content_bytes)} > {max_bytes}",
            )

        # Verify existing hash if requested
        if expected_sha256 and resolved.exists():
            existing_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
            if existing_hash != expected_sha256:
                return FsResult(
                    success=False,
                    data=None,
                    meta={"path": str(resolved), "actual_sha256": existing_hash},
                    error="SHA256 mismatch",
                )

        # Prevent writing to special files
        if resolved.exists():
            if resolved.is_fifo():
                return FsResult(
                    success=False,
                    data=None,
                    meta={"path": str(resolved)},
                    error=f"Cannot write to a FIFO: {resolved}",
                )
            # is_file() is False for FIFOs, so this is safe
            if not resolved.is_file():
                return FsResult(
                    success=False,
                    data=None,
                    meta={"path": str(resolved)},
                    error=f"Path is not a regular file: {resolved}",
                )


        # Write atomically for rewrite, direct for append
        if mode == "rewrite":
            tmp_path = resolved.with_suffix(resolved.suffix + ".tmp")
            tmp_path.write_bytes(content_bytes)
            tmp_path.replace(resolved)
        else:
            with open(resolved, "ab") as f:
                f.write(content_bytes)

        new_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
        return FsResult(
            success=True,
            data={"bytes_written": len(content_bytes), "new_sha256": new_hash},
            meta={"path": str(resolved)},
        )
    except PathSecurityError as e:
        return FsResult(success=False, data=None, meta={"path": str(path)}, error=str(e))
    except Exception as e:
        return FsResult(
            success=False, data=None, meta={"path": str(path)}, error=f"Write error: {e}"
        )


def create_directory(
    path: str | Path,
    allowed_roots: list[str],
    exist_ok: bool = True,
) -> FsResult:
    """Create a directory (and parents if needed)."""
    try:
        resolved = validate_path(path, allowed_roots)
        resolved.mkdir(parents=True, exist_ok=exist_ok)
        return FsResult(
            success=True,
            data={"created": True},
            meta={"path": str(resolved)},
        )
    except FileExistsError:
        return FsResult(
            success=False, data=None, meta={"path": str(path)}, error="Directory exists"
        )
    except PathSecurityError as e:
        return FsResult(success=False, data=None, meta={"path": str(path)}, error=str(e))
    except Exception as e:
        return FsResult(
            success=False, data=None, meta={"path": str(path)}, error=f"Mkdir error: {e}"
        )


def move_file(
    source: str | Path,
    dest: str | Path,
    allowed_roots: list[str],
) -> FsResult:
    """Move/rename a file or directory."""
    try:
        src_resolved = validate_path(source, allowed_roots)
        dst_resolved = validate_path(dest, allowed_roots)

        if not src_resolved.exists():
            return FsResult(
                success=False, data=None, meta={"source": str(source)}, error="Source not found"
            )

        shutil.move(str(src_resolved), str(dst_resolved))
        return FsResult(
            success=True,
            data={"source": str(src_resolved), "dest": str(dst_resolved)},
            meta={},
        )
    except PathSecurityError as e:
        return FsResult(success=False, data=None, meta={}, error=str(e))
    except Exception as e:
        return FsResult(success=False, data=None, meta={}, error=f"Move error: {e}")


def delete_file(
    path: str | Path,
    allowed_roots: list[str],
    recursive: bool = False,
) -> FsResult:
    """Delete a file or directory."""
    try:
        resolved = validate_path(path, allowed_roots)

        if not resolved.exists():
            return FsResult(
                success=False, data=None, meta={"path": str(path)}, error="Path not found"
            )

        # Safety: don't delete allowed roots themselves
        for root in allowed_roots:
            if resolved == Path(root).resolve():
                return FsResult(
                    success=False,
                    data=None,
                    meta={"path": str(path)},
                    error="Cannot delete allowed root",
                )

        if resolved.is_dir():
            if not recursive:
                return FsResult(
                    success=False,
                    data=None,
                    meta={"path": str(path)},
                    error="Is directory, use recursive=True",
                )
            shutil.rmtree(resolved)
        else:
            resolved.unlink()

        return FsResult(success=True, data={"deleted": str(resolved)}, meta={})
    except PathSecurityError as e:
        return FsResult(success=False, data=None, meta={"path": str(path)}, error=str(e))
    except Exception as e:
        return FsResult(
            success=False, data=None, meta={"path": str(path)}, error=f"Delete error: {e}"
        )


def edit_block(
    path: str | Path,
    allowed_roots: list[str],
    old_text: str,
    new_text: str,
    expected_replacements: int = 1,
) -> FsResult:
    """
    Surgical text replacement in a file.

    Args:
        path: File to edit
        allowed_roots: Allowed directories
        old_text: Text to find and replace
        new_text: Replacement text
        expected_replacements: Expected number of matches (default 1)

    Returns:
        FsResult with replacement count and snippets
    """
    try:
        resolved = validate_path(path, allowed_roots)

        if not resolved.exists():
            return FsResult(
                success=False, data=None, meta={"path": str(path)}, error="File not found"
            )
        if not resolved.is_file():
            return FsResult(success=False, data=None, meta={"path": str(path)}, error="Not a file")

        content = resolved.read_text(encoding="utf-8")
        count = content.count(old_text)

        if count == 0:
            # Try to find close match for helpful error
            return FsResult(
                success=False,
                data=None,
                meta={"path": str(path)},
                error="Text not found in file",
            )

        if count != expected_replacements:
            return FsResult(
                success=False,
                data=None,
                meta={"path": str(path), "actual_count": count},
                error=f"Expected {expected_replacements} matches, found {count}",
            )

        # Do the replacement
        new_content = content.replace(old_text, new_text)

        # Write atomically
        tmp_path = resolved.with_suffix(resolved.suffix + ".tmp")
        tmp_path.write_text(new_content, encoding="utf-8")
        tmp_path.replace(resolved)

        return FsResult(
            success=True,
            data={"replacements": count},
            meta={"path": str(resolved)},
        )
    except PathSecurityError as e:
        return FsResult(success=False, data=None, meta={"path": str(path)}, error=str(e))
    except UnicodeDecodeError:
        return FsResult(
            success=False, data=None, meta={"path": str(path)}, error="File is not UTF-8 text"
        )
    except Exception as e:
        return FsResult(
            success=False, data=None, meta={"path": str(path)}, error=f"Edit error: {e}"
        )
