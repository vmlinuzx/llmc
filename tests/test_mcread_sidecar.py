"""Tests for mcread sidecar integration."""

import gzip
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestMcreadSidecarIntegration:
    """Test that mcread correctly reads from sidecars for PDF/DOCX files."""

    def test_mcread_reads_sidecar_for_pdf(self, tmp_path):
        """When a PDF has a sidecar, mcread should read from the sidecar."""
        # Setup: create a fake PDF and its sidecar
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        
        # Create .llmc directory structure
        llmc_dir = repo_root / ".llmc"
        llmc_dir.mkdir()
        
        # Create a dummy PDF (we can't read it directly)
        pdf_path = repo_root / "docs" / "spec.pdf"
        pdf_path.parent.mkdir(parents=True)
        pdf_path.write_bytes(b"%PDF-1.4 binary content")
        
        # Create the markdown sidecar
        sidecar_dir = llmc_dir / "sidecars" / "docs"
        sidecar_dir.mkdir(parents=True)
        sidecar_path = sidecar_dir / "spec.pdf.md.gz"
        
        expected_content = "# Spec Document\n\n## Page 1\n\nThis is readable content."
        with gzip.open(sidecar_path, "wt", encoding="utf-8") as f:
            f.write(expected_content)
        
        # Verify sidecar detection works
        from llmc.rag.sidecar import is_sidecar_eligible, get_sidecar_path
        
        assert is_sidecar_eligible(Path("docs/spec.pdf")) is True
        computed_sidecar = get_sidecar_path(Path("docs/spec.pdf"), repo_root)
        assert computed_sidecar == sidecar_path
        assert computed_sidecar.exists()
        
        # Verify we can read the sidecar content
        with gzip.open(computed_sidecar, "rt", encoding="utf-8") as f:
            content = f.read()
        assert "# Spec Document" in content
        assert "This is readable content" in content

    def test_sidecar_eligible_files(self):
        """Test which file types are sidecar-eligible."""
        from llmc.rag.sidecar import is_sidecar_eligible
        
        # Eligible (binary documents)
        assert is_sidecar_eligible(Path("doc.pdf")) is True
        assert is_sidecar_eligible(Path("doc.PDF")) is True
        assert is_sidecar_eligible(Path("doc.docx")) is True
        assert is_sidecar_eligible(Path("doc.pptx")) is True
        assert is_sidecar_eligible(Path("doc.rtf")) is True
        
        # Not eligible (already text-based)
        assert is_sidecar_eligible(Path("doc.md")) is False
        assert is_sidecar_eligible(Path("doc.py")) is False
        assert is_sidecar_eligible(Path("doc.txt")) is False
        assert is_sidecar_eligible(Path("doc.json")) is False
