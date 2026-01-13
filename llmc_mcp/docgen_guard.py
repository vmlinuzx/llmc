"""
Docgen Coordinator - MAASL Phase 6

Provides SHA-gated, mutex-protected documentation generation.

Key Features:
- SHA256 gating: Skip docgen if source file hash matches doc header
- Repo-level mutex: Serialize docgen operations via IDEMP_DOCS lock
- Atomic writes: Temp file + rename for crash safety
- Status tracking: Circular buffer of recent docgen runs

Usage:
    coordinator = DocgenCoordinator(maasl, repo_root)
    result = coordinator.docgen_file(
        source_path="llmc/routing/query_type.py",
        agent_id="agent-1",
        session_id="sess-123",
        operation_mode="interactive"
    )

    if result.status == "noop":
        print(f"Doc already up to date (hash: {result.hash})")
    elif result.status == "generated":
        print(f"Generated {result.doc_path} in {result.duration_ms}ms")
"""

from collections import deque
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import tempfile
import time

from .docgen_engine import DocgenEngine
from .maasl import MAASL, ResourceDescriptor


@dataclass
class DocgenResult:
    """Result of a docgen operation."""

    status: str  # "generated", "noop", "skipped", "error"
    source_file: str
    doc_path: str | None = None
    hash: str | None = None
    duration_ms: int = 0
    error: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    timestamp: float = field(default_factory=time.time)


class DocgenCoordinator:
    """
    Coordinator for idempotent documentation generation.

    Responsibilities:
    - Compute SHA256 of source files
    - Check existing doc headers for matching hashes
    - Acquire IDEMP_DOCS lock for repo-level serialization
    - Generate documentation atomically
    - Track recent docgen operations

    Thread-safe via MAASL locking.
    """

    BUFFER_SIZE = 100  # Keep last 100 docgen results
    SHA_HEADER_PREFIX = "<!-- SHA256:"  # Doc header format: <!-- SHA256: abc123... -->

    def __init__(self, maasl: MAASL, repo_root: str, docs_dir: str = "DOCS/REPODOCS"):
        """
        Initialize docgen coordinator.

        Args:
            maasl: MAASL instance for locking
            repo_root: Absolute path to repository root
            docs_dir: Relative path from repo_root to docs directory
        """
        self.maasl = maasl
        self.repo_root = Path(repo_root).resolve()
        self.docs_dir = self.repo_root / docs_dir
        self.docs_dir.mkdir(parents=True, exist_ok=True)

        self.engine = DocgenEngine()

        # Circular buffer for status tracking (thread-safe due to deque)
        self._history: deque[DocgenResult] = deque(maxlen=self.BUFFER_SIZE)

    def compute_source_hash(self, source_path: str) -> str:
        """
        Compute SHA256 hash of source file.

        Args:
            source_path: Absolute path to source file

        Returns:
            Hex-encoded SHA256 hash

        Raises:
            FileNotFoundError: If source file doesn't exist
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        sha256 = hashlib.sha256()
        sha256.update(source.read_bytes())
        return sha256.hexdigest()

    def get_doc_path(self, source_path: str) -> Path:
        """
        Compute documentation path for a source file.

        Args:
            source_path: Absolute path to source file

        Returns:
            Absolute path to corresponding doc file
        """
        source = Path(source_path)

        # Get relative path from repo root
        try:
            rel_path = source.relative_to(self.repo_root)
        except ValueError:
            # File is outside repo, use basename
            rel_path = Path(source.name)

        # Convert to markdown filename
        doc_name = str(rel_path).replace("/", "_").replace("\\", "_") + ".md"
        return self.docs_dir / doc_name

    def read_doc_hash(self, doc_path: Path) -> str | None:
        """
        Extract SHA256 hash from existing doc header.

        Args:
            doc_path: Path to documentation file

        Returns:
            SHA256 hash if found, None otherwise
        """
        if not doc_path.exists():
            return None

        try:
            first_line = doc_path.read_text(encoding="utf-8").split("\n")[0]
            if first_line.startswith(self.SHA_HEADER_PREFIX):
                # Extract hash: <!-- SHA256: abc123... -->
                hash_part = first_line[len(self.SHA_HEADER_PREFIX) :].strip()
                if hash_part.endswith("-->"):
                    return hash_part[:-3].strip()
        except (OSError, IndexError):
            pass

        return None

    def generate_doc_content(self, source_path: str, source_hash: str) -> str:
        """
        Generate documentation content for a source file.

        Args:
            source_path: Absolute path to source file
            source_hash: SHA256 hash of source file

        Returns:
            Generated markdown content
        """
        source = Path(source_path)
        rel_path = (
            source.relative_to(self.repo_root)
            if source.is_relative_to(self.repo_root)
            else source.name
        )

        # Read source code
        try:
            source_code = source.read_text(encoding="utf-8")
            generated_body = self.engine.generate(source_code, str(source))
        except Exception as e:
            generated_body = f"*Error reading source:* {e}"

        # Header with SHA256
        content = f"{self.SHA_HEADER_PREFIX} {source_hash} -->\n"
        content += f"# Documentation: {rel_path}\n\n"
        content += f"**Source:** `{rel_path}`  \n"
        content += f"**Hash:** `{source_hash}`  \n"
        content += f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  \n\n"
        content += "## Overview\n\n"
        content += f"*Auto-generated documentation for `{source.name}`.*\n\n"
        content += "## Contents\n\n"
        content += generated_body

        return content

    def atomic_write(self, path: Path, content: str) -> None:
        """
        Atomically write content to file using temp + rename.

        Args:
            path: Target file path
            content: Content to write
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file in same directory (for atomic rename)
        fd, temp_path = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )

        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)

            # Atomic rename
            os.replace(temp_path, path)
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def docgen_file(
        self,
        source_path: str,
        agent_id: str,
        session_id: str,
        operation_mode: str = "interactive",
    ) -> DocgenResult:
        """
        Generate documentation for a source file with SHA gating.

        SECURITY: Only files within repo_root are allowed.

        Workflow:
        1. SECURITY: Validate source_path is within repo_root
        2. Compute SHA256 of source file
        3. Check existing doc header for matching hash
        4. If match, return NO-OP (doc is up to date)
        5. Acquire IDEMP_DOCS lock (repo-level mutex)
        6. Generate documentation
        7. Write atomically with SHA header
        8. Release lock and return result

        Args:
            source_path: Absolute path to source file
            agent_id: ID of requesting agent
            session_id: Session ID
            operation_mode: "interactive" or "batch"

        Returns:
            DocgenResult with status and metadata

        Raises:
            ValueError: If source_path is outside repo_root
        """
        start_time = time.time()

        # SECURITY: Validate path is within repository
        source = Path(source_path).resolve()
        try:
            source.relative_to(self.repo_root)
        except ValueError:
            raise ValueError(
                f"Access denied: '{source_path}' is not within repository root. "
                f"Only files within {self.repo_root} are allowed."
            )

        try:
            # 1. Compute source hash (now safe after validation)
            source_hash = self.compute_source_hash(source_path)
            doc_path = self.get_doc_path(source_path)

            # 2. Check if doc is already up to date
            existing_hash = self.read_doc_hash(doc_path)
            if existing_hash == source_hash:
                result = DocgenResult(
                    status="noop",
                    source_file=source_path,
                    doc_path=str(doc_path),
                    hash=source_hash,
                    duration_ms=int((time.time() - start_time) * 1000),
                    agent_id=agent_id,
                    session_id=session_id,
                )
                self._history.append(result)
                return result

            # 3. Acquire IDEMP_DOCS lock and generate
            docgen_desc = ResourceDescriptor("IDEMP_DOCS", "repo")

            def _generate():
                content = self.generate_doc_content(source_path, source_hash)
                self.atomic_write(doc_path, content)
                return str(doc_path)

            # MAASL-protected generation
            generated_path = self.maasl.call_with_stomp_guard(
                op=_generate,
                resources=[docgen_desc],
                intent="docgen_file",
                mode=operation_mode,
                agent_id=agent_id,
                session_id=session_id,
            )

            result = DocgenResult(
                status="generated",
                source_file=source_path,
                doc_path=generated_path,
                hash=source_hash,
                duration_ms=int((time.time() - start_time) * 1000),
                agent_id=agent_id,
                session_id=session_id,
            )
            self._history.append(result)
            return result

        except Exception as e:
            result = DocgenResult(
                status="error",
                source_file=source_path,
                hash=None,
                duration_ms=int((time.time() - start_time) * 1000),
                error=str(e),
                agent_id=agent_id,
                session_id=session_id,
            )
            self._history.append(result)
            raise

    def get_status(self, limit: int = 10) -> list[DocgenResult]:
        """
        Get recent docgen operation history.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of recent DocgenResult objects (newest first)
        """
        return list(self._history)[-limit:][::-1]
