#!/usr/bin/env python3
"""
MAASL Facade - Multi-Agent Anti-Stomp Layer coordination entry point.

Provides:
- ResourceClass definitions for different resource types
- PolicyRegistry for resource class configuration
- call_with_stomp_guard() wrapper for protected operations
- stomp_guard() context manager for long-running protected sections
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import logging
import time
from typing import Any

from llmc_mcp.locks import LockHandle, ResourceBusyError, get_lock_manager
from llmc_mcp.telemetry import get_telemetry_sink

logger = logging.getLogger("llmc-mcp.maasl")


@dataclass
class ResourceClass:
    """
    Resource class definition.

    Defines concurrency model and policy for a class of resources.
    """

    name: str
    concurrency: str  # "mutex", "single_writer", "merge", "idempotent"
    lock_scope: str  # "file", "db", "repo", "graph"
    lease_ttl_sec: int
    max_wait_ms: int  # Default for interactive mode
    batch_max_wait_ms: int  # For batch mode
    stomp_strategy: str  # "fail_closed", "fail_open_merge"


@dataclass
class ResourceDescriptor:
    """
    Describes a specific resource to be protected.

    Used by tool shims to specify what they need to lock.
    """

    resource_class: str  # e.g., "CRIT_CODE"
    identifier: str  # e.g., absolute path or logical resource ID


class PolicyRegistry:
    """
    Registry of resource classes and their policies.

    Provides mapping from ResourceDescriptor to ResourceClass
    and computes resource keys.
    """

    # Built-in resource class definitions (from SDD)
    BUILTIN_CLASSES = {
        "CRIT_CODE": ResourceClass(
            name="CRIT_CODE",
            concurrency="mutex",
            lock_scope="file",
            lease_ttl_sec=30,
            max_wait_ms=500,
            batch_max_wait_ms=3000,
            stomp_strategy="fail_closed",
        ),
        "CRIT_DB": ResourceClass(
            name="CRIT_DB",
            concurrency="single_writer",
            lock_scope="db",
            lease_ttl_sec=60,
            max_wait_ms=1000,
            batch_max_wait_ms=10000,
            stomp_strategy="fail_closed",
        ),
        "MERGE_META": ResourceClass(
            name="MERGE_META",
            concurrency="merge",
            lock_scope="graph",
            lease_ttl_sec=30,
            max_wait_ms=500,
            batch_max_wait_ms=5000,
            stomp_strategy="fail_open_merge",
        ),
        "IDEMP_DOCS": ResourceClass(
            name="IDEMP_DOCS",
            concurrency="idempotent",
            lock_scope="repo",
            lease_ttl_sec=120,
            max_wait_ms=500,
            batch_max_wait_ms=5000,
            stomp_strategy="fail_closed",
        ),
    }

    def __init__(self, config: dict | None = None):
        """
        Initialize policy registry.

        Args:
            config: Optional config dict from llmc.toml [maasl] section
        """
        self.classes = dict(self.BUILTIN_CLASSES)
        self.config = config or {}

        # Apply config overrides if present
        self._apply_config_overrides()

    def _apply_config_overrides(self):
        """Apply configuration overrides from llmc.toml."""
        if not self.config:
            return

        # Apply per-resource overrides
        for class_name, resource_class in self.classes.items():
            resource_config_key = f"resource.{class_name}"
            if resource_config_key in self.config:
                overrides = self.config[resource_config_key]

                if "lease_ttl_sec" in overrides:
                    resource_class.lease_ttl_sec = overrides["lease_ttl_sec"]
                if "interactive_max_wait_ms" in overrides:
                    resource_class.max_wait_ms = overrides["interactive_max_wait_ms"]
                if "batch_max_wait_ms" in overrides:
                    resource_class.batch_max_wait_ms = overrides["batch_max_wait_ms"]

                logger.debug(f"Applied config overrides to {class_name}: {overrides}")

    def get_resource_class(self, class_name: str) -> ResourceClass:
        """Get resource class by name."""
        if class_name not in self.classes:
            raise ValueError(f"Unknown resource class: {class_name}")
        return self.classes[class_name]

    def compute_resource_key(self, descriptor: ResourceDescriptor) -> str:
        """
        Compute canonical resource key from descriptor.

        Format: "{lock_scope}:{identifier}"
        Examples:
            - "code:/absolute/path/to/foo.py"
            - "db:rag"
            - "graph:main"
            - "docgen:repo"
        """
        resource_class = self.get_resource_class(descriptor.resource_class)
        scope = resource_class.lock_scope

        # For file-scoped resources, use absolute path
        if scope == "file":
            return f"code:{descriptor.identifier}"
        elif scope == "db":
            return f"db:{descriptor.identifier}"
        elif scope == "graph":
            return f"graph:{descriptor.identifier}"
        elif scope == "repo":
            return f"docgen:{descriptor.identifier}"
        else:
            return f"{scope}:{descriptor.identifier}"

    def get_max_wait_ms(self, resource_class: ResourceClass, mode: str) -> int:
        """Get max wait time based on mode."""
        if mode == "batch":
            return resource_class.batch_max_wait_ms
        else:
            return resource_class.max_wait_ms


# Exception hierarchy
class MAASLError(Exception):
    """Base exception for MAASL errors."""

    pass


class DbBusyError(MAASLError):
    """Database lock timeout."""

    def __init__(self, description: str, sqlite_error: str | None = None):
        self.description = description
        self.sqlite_error = sqlite_error
        super().__init__(description)


class DocgenStaleError(MAASLError):
    """Docgen SHA mismatch."""

    def __init__(self, file: str, expected_hash: str, got_hash: str):
        self.file = file
        self.expected_hash = expected_hash
        self.got_hash = got_hash
        super().__init__(
            f"Docgen stale: {file} (expected={expected_hash}, got={got_hash})"
        )


class StaleVersionError(MAASLError):
    """File version mismatch."""

    def __init__(self, file: str, expected_version: str, current_version: str):
        self.file = file
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"Stale version: {file} "
            f"(expected={expected_version}, current={current_version})"
        )


class MaaslInternalError(MAASLError):
    """Unexpected internal error."""

    def __init__(self, message: str, original_exception: Exception | None = None):
        self.message = message
        self.original_exception = original_exception
        super().__init__(message)


class MAASL:
    """
    Multi-Agent Anti-Stomp Layer facade.

    Provides call_with_stomp_guard() wrapper for protected operations.
    """

    def __init__(self, policy_registry: PolicyRegistry | None = None):
        self.policy = policy_registry or PolicyRegistry()
        self.lock_manager = get_lock_manager()
        self.telemetry = get_telemetry_sink()

    def call_with_stomp_guard(
        self,
        op: Callable[[], Any],
        resources: list[ResourceDescriptor],
        intent: str,
        mode: str,
        agent_id: str,
        session_id: str,
    ) -> Any:
        """
        Execute operation with stomping protection.

        Args:
            op: Callable to execute within protected section
            resources: List of resources to lock
            intent: Human-readable label (e.g., "write_file", "rag_enrich")
            mode: "interactive" or "batch"
            agent_id: ID of calling agent
            session_id: ID of calling session

        Returns:
            Result of op()

        Raises:
            ResourceBusyError: Lock acquisition timeout
            DbBusyError: Database transaction timeout
            DocgenStaleError: SHA mismatch
            StaleVersionError: File version conflict
            MaaslInternalError: Unexpected error
        """
        start_time = time.time()
        acquired_locks: list[LockHandle] = []

        try:
            # Step 1: Resolve descriptors to resource classes and keys
            lock_specs = []
            for desc in resources:
                resource_class = self.policy.get_resource_class(desc.resource_class)
                resource_key = self.policy.compute_resource_key(desc)
                max_wait_ms = self.policy.get_max_wait_ms(resource_class, mode)

                lock_specs.append(
                    {
                        "descriptor": desc,
                        "resource_class": resource_class,
                        "resource_key": resource_key,
                        "max_wait_ms": max_wait_ms,
                    }
                )

            # Step 2: Sort by resource_key for deadlock prevention
            lock_specs.sort(key=lambda x: x["resource_key"])

            # Step 3: Acquire locks in sorted order
            for spec in lock_specs:
                lock_handle = self.lock_manager.acquire(
                    resource_key=spec["resource_key"],
                    agent_id=agent_id,
                    session_id=session_id,
                    lease_ttl_sec=spec["resource_class"].lease_ttl_sec,
                    max_wait_ms=spec["max_wait_ms"],
                    mode=mode,
                )
                acquired_locks.append(lock_handle)

            # Step 4: Execute operation
            result = op()

            # Step 5: Log success
            duration_ms = (time.time() - start_time) * 1000
            self.telemetry.log_stomp_guard_call(
                intent=intent,
                mode=mode,
                agent_id=agent_id,
                session_id=session_id,
                resource_count=len(resources),
                duration_ms=duration_ms,
                success=True,
            )

            return result

        except ResourceBusyError:
            # Re-raise with telemetry
            duration_ms = (time.time() - start_time) * 1000
            self.telemetry.log_stomp_guard_call(
                intent=intent,
                mode=mode,
                agent_id=agent_id,
                session_id=session_id,
                resource_count=len(resources),
                duration_ms=duration_ms,
                success=False,
                error_type="ResourceBusyError",
            )
            raise

        except (DbBusyError, DocgenStaleError, StaleVersionError) as e:
            # Known MAASL errors - re-raise with telemetry
            duration_ms = (time.time() - start_time) * 1000
            self.telemetry.log_stomp_guard_call(
                intent=intent,
                mode=mode,
                agent_id=agent_id,
                session_id=session_id,
                resource_count=len(resources),
                duration_ms=duration_ms,
                success=False,
                error_type=type(e).__name__,
            )
            raise

        except Exception as e:
            # Unexpected error - wrap in MaaslInternalError
            duration_ms = (time.time() - start_time) * 1000
            self.telemetry.log_stomp_guard_call(
                intent=intent,
                mode=mode,
                agent_id=agent_id,
                session_id=session_id,
                resource_count=len(resources),
                duration_ms=duration_ms,
                success=False,
                error_type="MaaslInternalError",
            )
            logger.exception(f"Unexpected error in stomp guard for {intent}")
            raise MaaslInternalError(
                message=f"Unexpected error during {intent}: {str(e)}",
                original_exception=e,
            ) from None

        finally:
            # Step 6: Release all acquired locks (in reverse order)
            for lock_handle in reversed(acquired_locks):
                try:
                    self.lock_manager.release(
                        resource_key=lock_handle.resource_key,
                        agent_id=lock_handle.agent_id,
                        session_id=lock_handle.session_id,
                        fencing_token=lock_handle.fencing_token,
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to release lock {lock_handle.resource_key}: {e}"
                    )

    @contextmanager
    def stomp_guard(
        self,
        resources: list[ResourceDescriptor],
        intent: str,
        mode: str,
        agent_id: str,
        session_id: str,
    ) -> Iterator[list[LockHandle]]:
        """
        Context manager for long-running protected sections.

        Unlike call_with_stomp_guard(), this holds locks for the entire
        duration of the context block. Use for operations that need to
        yield control (e.g., database transactions with context managers).

        Args:
            resources: List of resources to lock
            intent: Human-readable label (e.g., "db_write", "file_update")
            mode: "interactive" or "batch"
            agent_id: ID of calling agent
            session_id: ID of calling session

        Yields:
            List of acquired lock handles

        Raises:
            ResourceBusyError: Lock acquisition timeout
            MaaslInternalError: Unexpected error during lock acquisition

        Example:
            >>> with maasl.stomp_guard(resources, "db_write", "interactive", ...) as locks:
            ...     # Lock is held for entire block
            ...     conn.execute("BEGIN IMMEDIATE")
            ...     conn.execute("INSERT INTO ...")
            ...     conn.commit()
        """
        start_time = time.time()
        acquired_locks: list[LockHandle] = []
        success = False
        error_type: str | None = None

        try:
            # Step 1: Resolve descriptors to resource classes and keys
            lock_specs = []
            for desc in resources:
                resource_class = self.policy.get_resource_class(desc.resource_class)
                resource_key = self.policy.compute_resource_key(desc)
                max_wait_ms = self.policy.get_max_wait_ms(resource_class, mode)

                lock_specs.append(
                    {
                        "descriptor": desc,
                        "resource_class": resource_class,
                        "resource_key": resource_key,
                        "max_wait_ms": max_wait_ms,
                    }
                )

            # Step 2: Sort by resource_key for deadlock prevention
            lock_specs.sort(key=lambda x: x["resource_key"])

            # Step 3: Acquire locks in sorted order
            for spec in lock_specs:
                lock_handle = self.lock_manager.acquire(
                    resource_key=spec["resource_key"],
                    agent_id=agent_id,
                    session_id=session_id,
                    lease_ttl_sec=spec["resource_class"].lease_ttl_sec,
                    max_wait_ms=spec["max_wait_ms"],
                    mode=mode,
                )
                acquired_locks.append(lock_handle)

            # Step 4: Yield with locks held
            yield acquired_locks
            success = True

        except ResourceBusyError:
            error_type = "ResourceBusyError"
            raise

        except (DbBusyError, DocgenStaleError, StaleVersionError) as e:
            error_type = type(e).__name__
            raise

        except MaaslInternalError:
            # Don't double-wrap MAASL errors
            error_type = "MaaslInternalError"
            raise

        except Exception:
            # User exceptions should propagate unchanged
            # Only set error flag for telemetry, don't wrap
            error_type = "UserException"
            raise

        finally:
            # Step 5: Release all acquired locks (in reverse order)
            for lock_handle in reversed(acquired_locks):
                try:
                    self.lock_manager.release(
                        resource_key=lock_handle.resource_key,
                        agent_id=lock_handle.agent_id,
                        session_id=lock_handle.session_id,
                        fencing_token=lock_handle.fencing_token,
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to release lock {lock_handle.resource_key}: {e}"
                    )

            # Step 6: Log telemetry
            duration_ms = (time.time() - start_time) * 1000
            self.telemetry.log_stomp_guard_call(
                intent=intent,
                mode=mode,
                agent_id=agent_id,
                session_id=session_id,
                resource_count=len(resources),
                duration_ms=duration_ms,
                success=success,
                error_type=error_type,
            )


# Global singleton instance
_maasl: MAASL | None = None


def get_maasl(config: dict | None = None) -> MAASL:
    """Get or create global MAASL instance."""
    global _maasl
    if _maasl is None:
        policy = PolicyRegistry(config=config)
        _maasl = MAASL(policy_registry=policy)
    return _maasl


def configure_maasl(config: dict):
    """Configure global MAASL instance."""
    global _maasl
    policy = PolicyRegistry(config=config)
    _maasl = MAASL(policy_registry=policy)
