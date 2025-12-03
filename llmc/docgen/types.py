"""
Core types for the docgen module.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class DocgenResult:
    """Result of a documentation generation operation."""
    
    status: str  # "noop" | "generated" | "skipped" | "error"
    sha256: str
    output_markdown: str | None
    reason: str | None = None
    
    def __post_init__(self):
        """Validate status field."""
        valid_statuses = {"noop", "generated", "skipped", "error"}
        if self.status not in valid_statuses:
            raise ValueError(
                f"Invalid status '{self.status}'. "
                f"Must be one of: {', '.join(sorted(valid_statuses))}"
            )


class DocgenBackend(Protocol):
    """Protocol for documentation generation backends.
    
    Backends are responsible for generating documentation for a single file,
    given the source contents and optional graph context.
    """
    
    def generate_for_file(
        self,
        repo_root: Path,
        relative_path: Path,
        file_sha256: str,
        source_contents: str,
        existing_doc_contents: str | None,
        graph_context: str | None,
    ) -> DocgenResult:
        """Generate documentation for a single file.
        
        Args:
            repo_root: Absolute path to repository root
            relative_path: Path relative to repo root
            file_sha256: SHA256 hash of source file
            source_contents: Contents of source file
            existing_doc_contents: Contents of existing doc (if any)
            graph_context: Graph context from RAG (if available)
            
        Returns:
            DocgenResult with status and generated content
        """
        ...
