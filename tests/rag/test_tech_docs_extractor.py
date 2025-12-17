import pytest
from pathlib import Path
from llmc.rag.extractors.tech_docs import TechDocsExtractor, TechDocsSpan

@pytest.fixture
def extractor():
    return TechDocsExtractor()

def test_markdown_heading_hierarchy(extractor):
    md = """# H1
Text 1.

## H2
Text 2.

### H3
Text 3.

## H2-B
Text 4.
"""
    spans = list(extractor.extract(Path("test.md"), md))
    # Chunks: H1, H2, H3, H2-B
    assert len(spans) == 4
    
    assert spans[0].section_path == "H1"
    assert "Text 1" in spans[0].content
    
    assert spans[1].section_path == "H1 > H2"
    assert "Text 2" in spans[1].content
    
    assert spans[2].section_path == "H1 > H2 > H3"
    assert "Text 3" in spans[2].content
    
    assert spans[3].section_path == "H1 > H2-B"
    assert "Text 4" in spans[3].content

def test_code_block_preservation(extractor):
    md = """# Code Test
Here is code:
```python
def hello():
    print("world")
```
End.
"""
    spans = list(extractor.extract(Path("code.md"), md))
    assert len(spans) == 1
    content = spans[0].content
    assert "```python" in content
    assert 'print("world")' in content
    assert "End." in content

def test_section_path_building(extractor):
    md = """# Install
## Prerequisites
### Step 1
"""
    spans = list(extractor.extract(Path("path.md"), md))
    assert spans[2].section_path == "Install > Prerequisites > Step 1"

def test_deterministic_chunking(extractor):
    md = """# Title
Some content.
"""
    spans1 = list(extractor.extract(Path("det.md"), md))
    spans2 = list(extractor.extract(Path("det.md"), md))
    
    assert len(spans1) == len(spans2)
    assert spans1[0].content == spans2[0].content
    assert spans1[0].metadata['anchor'] == spans2[0].metadata['anchor']

def test_anchor_generation(extractor):
    md = "# My Cool Header"
    spans = list(extractor.extract(Path("anchor.md"), md))
    assert spans[0].metadata['anchor'] == "anchor.md#my-cool-header"

def test_anchor_uniqueness(extractor):
    md = """# Intro
## Section
Text A.
## Section
Text B.
"""
    spans = list(extractor.extract(Path("unique.md"), md))
    assert len(spans) == 3
    # Intro
    # Section 1
    # Section 2
    
    # Check anchors
    anchors = [s.metadata['anchor'] for s in spans]
    # Anchors should be unique
    assert len(set(anchors)) == len(anchors)
    
    # Specific check
    # First section should be 'section'
    # Second should be 'section-1'
    
    # Note: indices depend on iteration order.
    # spans[1] is the first "Section"
    # spans[2] is the second "Section"
    
    assert "unique.md#section" in anchors
    assert "unique.md#section-1" in anchors
