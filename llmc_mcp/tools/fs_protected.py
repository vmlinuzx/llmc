#!/usr/bin/env python3
"""
MAASL-protected filesystem write operations.

Phase 3: Code Protection - wraps file write operations with stomping protection.
"""

from __future__ import annotations

from pathlib import Path

from llmc_mcp.maasl import ResourceBusyError, ResourceDescriptor, get_maasl
from llmc_mcp.tools.fs import (
    FsResult,
    delete_file as _delete_file_unprotected,
    edit_block as _edit_block_unprotected,
    move_file as _move_file_unprotected,
    validate_path,
    write_file as _write_file_unprotected,
)


def write_file_protected(
    path: str | Path,
    allowed_roots: list[str],
    content: str,
    mode: str = "rewrite",
    expected_sha256: str | None = None,
    max_bytes: int = 10_485_760,
    agent_id: str = "unknown",
    session_id: str = "unknown",
    operation_mode: str = "interactive",
) -> FsResult:
    """
    Write file with MAASL stomping protection.

    Args:
        path: File path to write
        allowed_roots: Allowed root directories
        content: Text content to write
        mode: "rewrite" (overwrite) or "append"
        expected_sha256: If provided, verify existing file hash before write
        max_bytes: Maximum bytes allowed to write
        agent_id: ID of calling agent
        session_id: ID of calling session
        operation_mode: "interactive" or "batch" (affects lock timeout)

    Returns:
        FsResult with bytes_written and new_sha256

    Raises:
        ResourceBusyError: Lock acquisition timeout (another agent has the file)
    """
    # Resolve path early for lock key
    try:
        resolved = validate_path(path, allowed_roots)
    except Exception as e:
        # Path validation failed - return error without locking
        return FsResult(
            success=False,
            data=None,
            meta={"path": str(path)},
            error=f"Path validation failed: {e}",
        )

    # Create resource descriptor
    resource = ResourceDescriptor(
        resource_class="CRIT_CODE",
        identifier=str(resolved),
    )

    # Define operation that will run within protected section
    def protected_write():
        return _write_file_unprotected(
            path=resolved,
            allowed_roots=allowed_roots,
            content=content,
            mode=mode,
            expected_sha256=expected_sha256,
            max_bytes=max_bytes,
        )

    # Execute with stomping protection
    maasl = get_maasl()
    try:
        return maasl.call_with_stomp_guard(
            op=protected_write,
            resources=[resource],
            intent="write_file",
            mode=operation_mode,
            agent_id=agent_id,
            session_id=session_id,
        )
    except ResourceBusyError as e:
        # Convert to FsResult for consistent error handling
        return FsResult(
            success=False,
            data=None,
            meta={
                "path": str(resolved),
                "resource_key": e.resource_key,
                "holder_agent_id": e.holder_agent_id,
                "wait_ms": e.wait_ms,
                "max_wait_ms": e.max_wait_ms,
            },
            error=f"File locked by {e.holder_agent_id}: {str(e)}",
        )


def edit_block_protected(
    path: str | Path,
    allowed_roots: list[str],
    old_text: str,
    new_text: str,
    expected_replacements: int = 1,
    agent_id: str = "unknown",
    session_id: str = "unknown",
    operation_mode: str = "interactive",
) -> FsResult:
    """
    Edit file with MAASL stomping protection.

    Args:
        path: File to edit
        allowed_roots: Allowed directories
        old_text: Text to find and replace
        new_text: Replacement text
        expected_replacements: Expected number of matches
        agent_id: ID of calling agent
        session_id: ID of calling session
        operation_mode: "interactive" or "batch"

    Returns:
        FsResult with replacement count
    """
    try:
        resolved = validate_path(path, allowed_roots)
    except Exception as e:
        return FsResult(
            success=False,
            data=None,
            meta={"path": str(path)},
            error=f"Path validation failed: {e}",
        )

    resource = ResourceDescriptor(
        resource_class="CRIT_CODE",
        identifier=str(resolved),
    )

    def protected_edit():
        return _edit_block_unprotected(
            path=resolved,
            allowed_roots=allowed_roots,
            old_text=old_text,
            new_text=new_text,
            expected_replacements=expected_replacements,
        )

    maasl = get_maasl()
    try:
        return maasl.call_with_stomp_guard(
            op=protected_edit,
            resources=[resource],
            intent="edit_file",
            mode=operation_mode,
            agent_id=agent_id,
            session_id=session_id,
        )
    except ResourceBusyError as e:
        return FsResult(
            success=False,
            data=None,
            meta={
                "path": str(resolved),
                "resource_key": e.resource_key,
                "holder_agent_id": e.holder_agent_id,
            },
            error=f"File locked by {e.holder_agent_id}: {str(e)}",
        )


def move_file_protected(
    source: str | Path,
    dest: str | Path,
    allowed_roots: list[str],
    agent_id: str = "unknown",
    session_id: str = "unknown",
    operation_mode: str = "interactive",
) -> FsResult:
    """
    Move/rename file with MAASL stomping protection.

    Locks BOTH source and destination paths to prevent races.

    Args:
        source: Source path
        dest: Destination path
        allowed_roots: Allowed directories
        agent_id: ID of calling agent
        session_id: ID of calling session
        operation_mode: "interactive" or "batch"

    Returns:
        FsResult with source and dest paths
    """
    try:
        src_resolved = validate_path(source, allowed_roots)
        dst_resolved = validate_path(dest, allowed_roots)
    except Exception as e:
        return FsResult(
            success=False,
            data=None,
            meta={},
            error=f"Path validation failed: {e}",
        )

    # Lock both source and destination
    resources = [
        ResourceDescriptor(resource_class="CRIT_CODE", identifier=str(src_resolved)),
        ResourceDescriptor(resource_class="CRIT_CODE", identifier=str(dst_resolved)),
    ]

    def protected_move():
        return _move_file_unprotected(
            source=src_resolved,
            dest=dst_resolved,
            allowed_roots=allowed_roots,
        )

    maasl = get_maasl()
    try:
        return maasl.call_with_stomp_guard(
            op=protected_move,
            resources=resources,
            intent="move_file",
            mode=operation_mode,
            agent_id=agent_id,
            session_id=session_id,
        )
    except ResourceBusyError as e:
        return FsResult(
            success=False,
            data=None,
            meta={"resource_key": e.resource_key, "holder_agent_id": e.holder_agent_id},
            error=f"Path locked by {e.holder_agent_id}: {str(e)}",
        )


def delete_file_protected(
    path: str | Path,
    allowed_roots: list[str],
    recursive: bool = False,
    agent_id: str = "unknown",
    session_id: str = "unknown",
    operation_mode: str = "interactive",
) -> FsResult:
    """
    Delete file with MAASL stomping protection.

    Args:
        path: Path to delete
        allowed_roots: Allowed directories
        recursive: Required for directories
        agent_id: ID of calling agent
        session_id: ID of calling session
        operation_mode: "interactive" or "batch"

    Returns:
        FsResult with deleted path
    """
    try:
        resolved = validate_path(path, allowed_roots)
    except Exception as e:
        return FsResult(
            success=False,
            data=None,
            meta={"path": str(path)},
            error=f"Path validation failed: {e}",
        )

    resource = ResourceDescriptor(
        resource_class="CRIT_CODE",
        identifier=str(resolved),
    )

    def protected_delete():
        return _delete_file_unprotected(
            path=resolved,
            allowed_roots=allowed_roots,
            recursive=recursive,
        )

    maasl = get_maasl()
    try:
        return maasl.call_with_stomp_guard(
            op=protected_delete,
            resources=[resource],
            intent="delete_file",
            mode=operation_mode,
            agent_id=agent_id,
            session_id=session_id,
        )
    except ResourceBusyError as e:
        return FsResult(
            success=False,
            data=None,
            meta={
                "path": str(resolved),
                "resource_key": e.resource_key,
                "holder_agent_id": e.holder_agent_id,
            },
            error=f"File locked by {e.holder_agent_id}: {str(e)}",
        )
