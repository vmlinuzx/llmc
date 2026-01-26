"""Test TreeSitterNav."""

from llmc.rlm.nav.treesitter_nav import TreeSitterNav


class TestTreeSitterNav:
    def test_uses_correct_llmc_imports(self, sample_python_code):
        """V1.1.1: Verify correct import paths."""
        # This test verifies the module loads without import errors
        nav = TreeSitterNav(sample_python_code, language="python")
        
        assert nav.language == "python"
        assert "greet" in str(nav.ls())
    
    def test_read_pagination(self):
        """V1.1.1 FIX: read() supports chunk_index parameter."""
        # Generate large function
        code = "def big():\n" + "    x = 1\n" * 500
        nav = TreeSitterNav(code, language="python")
        
        chunk0 = nav.read("big", chunk_index=0, max_chars=1000)
        chunk1 = nav.read("big", chunk_index=1, max_chars=1000)
        
        assert "chunk 1/" in chunk0
        assert "chunk 2/" in chunk1
        assert chunk0 != chunk1
    
    def test_outline_uses_skeletonizer(self, sample_python_code):
        """Outline uses existing Skeletonizer."""
        nav = TreeSitterNav(sample_python_code, language="python")
        outline = nav.outline()
        
        assert "Calculator" in outline
        assert "greet" in outline
    
    def test_ls_filters_by_scope(self, sample_python_code):
        """ls() can filter by scope."""
        nav = TreeSitterNav(sample_python_code, language="python")
        
        # Top-level
        top = nav.ls()
        assert any("greet" in sig for sig in top)
        assert any("Calculator" in sig for sig in top)
        
        # Class scope
        calc_methods = nav.ls("Calculator")
        assert any("add" in sig for sig in calc_methods)
        assert any("multiply" in sig for sig in calc_methods)
    
    def test_search_regex(self, sample_python_code):
        """search() finds regex matches."""
        nav = TreeSitterNav(sample_python_code, language="python")
        
        matches = nav.search(r"def \w+")
        assert len(matches) > 0
        assert any("def greet" in m.text for m in matches)
    
    def test_get_info(self, sample_python_code):
        """get_info() returns metadata."""
        nav = TreeSitterNav(sample_python_code, language="python")
        info = nav.get_info()
        
        assert info["language"] == "python"
        assert info["total_chars"] > 0
        assert info["total_lines"] > 0
        assert info["symbol_count"] > 0
