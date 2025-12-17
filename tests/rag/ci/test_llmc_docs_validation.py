"""
CI validation test for LLMC's own documentation.

Phase 5 of Domain RAG Tech Docs: Validate TechDocsExtractor
on LLMC's DOCS/ folder to ensure no regressions in parsing.
"""

import importlib.util
from pathlib import Path

import pytest


# Skip if mistune not available
pytestmark = pytest.mark.skipif(
    not importlib.util.find_spec("mistune"),
    reason="mistune not installed"
)


def test_llmc_docs_extraction():
    """Validate TechDocsExtractor on LLMC's own DOCS/ folder."""
    from llmc.rag.extractors.tech_docs import TechDocsExtractor
    
    # Find LLMC DOCS directory (relative to test file)
    test_file = Path(__file__)
    repo_root = test_file.parent.parent.parent.parent  # tests/rag/ci -> tests -> llmc
    docs_dir = repo_root / "DOCS"
    
    assert docs_dir.exists(), f"DOCS directory not found at {docs_dir}"
    
    extractor = TechDocsExtractor()
    total_files = 0
    total_chunks = 0
    zero_chunk_files = []
    
    for md_file in docs_dir.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            chunks = list(extractor.extract(md_file, content))
            total_files += 1
            total_chunks += len(chunks)
            
            if len(chunks) == 0:
                zero_chunk_files.append(str(md_file.relative_to(docs_dir)))
        except Exception as e:
            pytest.fail(f"Failed to extract {md_file}: {e}")
    
    # Assertions
    assert total_files >= 50, f"Expected at least 50 docs, got {total_files}"
    assert total_chunks >= 500, f"Expected at least 500 chunks, got {total_chunks}"
    
    # Allow a small number of empty files (e.g., index stubs)
    max_empty_allowed = 5
    assert len(zero_chunk_files) <= max_empty_allowed, (
        f"Too many files with 0 chunks ({len(zero_chunk_files)}): {zero_chunk_files[:10]}"
    )


def test_llmc_docs_chunk_quality():
    """Validate chunk quality metrics on LLMC docs."""
    from llmc.rag.extractors.tech_docs import TechDocsExtractor
    
    test_file = Path(__file__)
    repo_root = test_file.parent.parent.parent.parent
    docs_dir = repo_root / "DOCS"
    
    extractor = TechDocsExtractor()
    
    # Check a few key documentation files
    required_files = [
        "ARCHITECTURE.md",
        "roadmap.md",
    ]
    
    for filename in required_files:
        file_path = docs_dir / filename
        if not file_path.exists():
            pytest.skip(f"{filename} not found")
            continue
            
        content = file_path.read_text(encoding="utf-8")
        chunks = list(extractor.extract(file_path, content))
        
        # Quality assertions
        assert len(chunks) >= 3, f"{filename} should have at least 3 chunks"
        
        # Check that section paths are being extracted
        has_section_paths = any(
            hasattr(c, 'section_path') and c.section_path 
            for c in chunks
        )
        assert has_section_paths, f"{filename} chunks should have section_path"
        
        # Check that anchors are being generated
        has_anchors = any(
            hasattr(c, 'metadata') and c.metadata.get('anchor')
            for c in chunks
        )
        assert has_anchors, f"{filename} chunks should have anchors"


def test_llmc_docs_deterministic():
    """Validate that extraction is deterministic."""
    from llmc.rag.extractors.tech_docs import TechDocsExtractor
    
    test_file = Path(__file__)
    repo_root = test_file.parent.parent.parent.parent
    roadmap = repo_root / "DOCS" / "roadmap.md"
    
    if not roadmap.exists():
        pytest.skip("roadmap.md not found")
    
    extractor = TechDocsExtractor()
    content = roadmap.read_text(encoding="utf-8")
    
    # Extract twice
    chunks1 = list(extractor.extract(roadmap, content))
    chunks2 = list(extractor.extract(roadmap, content))
    
    # Same count
    assert len(chunks1) == len(chunks2), "Chunk count should be deterministic"
    
    # Same content
    for c1, c2 in zip(chunks1, chunks2):
        assert c1.content == c2.content, "Chunk content should be deterministic"
        assert c1.section_path == c2.section_path, "Section paths should be deterministic"
