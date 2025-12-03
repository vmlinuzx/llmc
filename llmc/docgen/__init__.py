"""
Deterministic documentation generation module.

This module provides RAG-aware, idempotent documentation generation
for repository files with SHA256-based change detection and graph context.
"""

from llmc.docgen.config import load_docgen_backend
from llmc.docgen.types import DocgenBackend, DocgenResult

__all__ = [
    "DocgenBackend",
    "DocgenResult",
    "load_docgen_backend",
]
