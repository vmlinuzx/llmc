"""
Orchestrator for docgen - coordinates the full documentation generation pipeline.
"""

import logging
from pathlib import Path
from typing import Any

from llmc.docgen.gating import (
    check_rag_freshness,
    compute_file_sha256,
    resolve_doc_path,
    should_skip_sha_gate,
    validate_source_path,
)
from llmc.docgen.graph_context import build_graph_context
from llmc.docgen.types import DocgenBackend, DocgenResult

logger = logging.getLogger(__name__)


class DocgenOrchestrator:
    """Orchestrates documentation generation for repository files.

    Coordinates SHA gating, RAG freshness checks, graph context building,
    backend invocation, and file writing.
    """

    def __init__(
        self,
        repo_root: Path,
        backend: DocgenBackend,
        db: Any,  # Database instance
        output_dir: str = "DOCS/REPODOCS",
        require_rag_fresh: bool = True,
    ):
        """Initialize orchestrator.

        Args:
            repo_root: Absolute path to repository root
            backend: Docgen backend instance
            db: RAG database instance
            output_dir: Output directory relative to repo root
            require_rag_fresh: Whether to require RAG freshness
        """
        self.repo_root = repo_root
        self.backend = backend
        self.db = db
        self.output_dir = output_dir
        self.require_rag_fresh = require_rag_fresh

    def process_file(
        self,
        relative_path: Path,
        force: bool = False,
        cached_graph: dict | None = None,
    ) -> DocgenResult:
        """Process a single file for documentation generation.

        Args:
            relative_path: Path relative to repo root
            force: Skip SHA gate if True
            cached_graph: Optional pre-loaded graph data (for batch processing)

        Returns:
            DocgenResult with status and outcome
        """
        logger.info(f"Processing {relative_path}")

        # Validate source path security
        try:
            source_path = validate_source_path(self.repo_root, relative_path)
        except ValueError as e:
            logger.warning(f"Security validation failed for {relative_path}: {e}")
            return DocgenResult(
                status="skipped",
                sha256="",
                output_markdown=None,
                reason=f"Security validation failed: {e}",
            )

        # Resolve output path
        doc_path = resolve_doc_path(self.repo_root, relative_path, self.output_dir)

        # Check source file exists
        if not source_path.exists():
            return DocgenResult(
                status="skipped",
                sha256="",
                output_markdown=None,
                reason=f"Source file not found: {source_path}",
            )

        # Compute SHA256
        try:
            file_sha256 = compute_file_sha256(source_path)
        except Exception as e:
            logger.error(f"Failed to compute SHA for {source_path}: {e}")
            return DocgenResult(
                status="skipped",
                sha256="",
                output_markdown=None,
                reason=f"Failed to compute SHA256: {e}",
            )

        # Gate 1: SHA256 check (unless forced)
        if not force:
            should_skip, skip_reason = should_skip_sha_gate(source_path, doc_path)
            if should_skip:
                logger.debug(f"Skipping {relative_path}: {skip_reason}")
                return DocgenResult(
                    status="noop",
                    sha256=file_sha256,
                    output_markdown=None,
                    reason=skip_reason,
                )

        # Gate 2: RAG freshness check (if required)
        if self.require_rag_fresh:
            is_fresh, freshness_reason = check_rag_freshness(
                self.db, relative_path, file_sha256
            )
            if not is_fresh:
                logger.debug(f"Skipping {relative_path}: {freshness_reason}")
                return DocgenResult(
                    status="skipped",
                    sha256=file_sha256,
                    output_markdown=None,
                    reason=freshness_reason,
                )

        # Read source contents
        try:
            with open(source_path, encoding="utf-8") as f:
                source_contents = f.read()
        except Exception as e:
            logger.error(f"Failed to read {source_path}: {e}")
            return DocgenResult(
                status="skipped",
                sha256=file_sha256,
                output_markdown=None,
                reason=f"Failed to read source file: {e}",
            )

        # Read existing doc if present
        existing_doc_contents = None
        if doc_path.exists():
            try:
                with open(doc_path, encoding="utf-8") as f:
                    existing_doc_contents = f.read()
            except Exception as e:
                logger.warning(f"Failed to read existing doc {doc_path}: {e}")

        # Build graph context
        try:
            graph_context = build_graph_context(
                self.repo_root,
                relative_path,
                self.db,
                cached_graph=cached_graph,
            )
        except Exception as e:
            logger.warning(f"Failed to build graph context: {e}")
            graph_context = None

        # Invoke backend
        logger.info(f"Generating docs for {relative_path}")
        result = self.backend.generate_for_file(
            repo_root=self.repo_root,
            relative_path=relative_path,
            file_sha256=file_sha256,
            source_contents=source_contents,
            existing_doc_contents=existing_doc_contents,
            graph_context=graph_context,
        )

        # Write doc file if generated
        if result.status == "generated" and result.output_markdown:
            try:
                self._write_doc_file(doc_path, result.output_markdown)
                logger.info(f"✅ Generated doc: {doc_path}")
            except Exception as e:
                logger.error(f"Failed to write doc {doc_path}: {e}")
                return DocgenResult(
                    status="skipped",
                    sha256=file_sha256,
                    output_markdown=None,
                    reason=f"Failed to write doc file: {e}",
                )

        return result

    def process_batch(
        self,
        file_paths: list[Path],
        force: bool = False,
        use_lock: bool = True,
    ) -> dict[str, DocgenResult]:
        """Process a batch of files for documentation generation.

        Args:
            file_paths: List of paths relative to repo root
            force: Skip SHA gate if True
            use_lock: Use file lock to prevent concurrent runs

        Returns:
            Dict mapping file path to result
        """
        # Acquire lock if requested
        if use_lock:
            from llmc.docgen.locks import DocgenLock

            with DocgenLock(self.repo_root):
                return self._process_batch_impl(file_paths, force)
        else:
            return self._process_batch_impl(file_paths, force)

    def _process_batch_impl(
        self,
        file_paths: list[Path],
        force: bool = False,
    ) -> dict[str, DocgenResult]:
        """Internal implementation of batch processing."""
        # Load graph indices ONCE for the entire batch (performance optimization)
        from llmc.docgen.graph_context import load_graph_indices

        logger.info(f"Loading graph indices for batch of {len(file_paths)} files...")
        cached_graph = load_graph_indices(self.repo_root)
        if cached_graph:
            entity_count = len(cached_graph.get("entities", {}))
            relation_count = len(cached_graph.get("relations", []))
            logger.info(
                f"Loaded graph: {entity_count} entities, {relation_count} relations"
            )
        else:
            logger.info("No graph indices found, proceeding without graph context")

        results = {}

        for rel_path in file_paths:
            try:
                # Pass cached graph to avoid repeated loading
                result = self.process_file(
                    rel_path, force=force, cached_graph=cached_graph
                )
                results[str(rel_path)] = result
            except Exception as e:
                # Log error but continue processing other files
                logger.error(f"❌ Failed to process {rel_path}: {e}", exc_info=True)
                results[str(rel_path)] = DocgenResult(
                    status="error",
                    sha256="",
                    output_markdown=None,
                    reason=f"Unhandled exception during processing: {e}",
                )

        # Log summary
        total = len(results)
        generated = sum(1 for r in results.values() if r.status == "generated")
        noop = sum(1 for r in results.values() if r.status == "noop")
        skipped = sum(1 for r in results.values() if r.status == "skipped")
        errors = sum(1 for r in results.values() if r.status == "error")

        logger.info(
            f"Batch complete: {total} files - "
            f"{generated} generated, {noop} noop, {skipped} skipped, {errors} errors"
        )

        return results

    def _write_doc_file(self, doc_path: Path, content: str) -> None:
        """Write documentation file atomically.

        Args:
            doc_path: Path to documentation file
            content: Documentation content
        """
        # Create parent directories
        doc_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file
        tmp_path = doc_path.with_suffix(".tmp")

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Atomic rename
            tmp_path.replace(doc_path)
        except Exception:
            # Clean up temp file on error
            if tmp_path.exists():
                tmp_path.unlink()
            raise
