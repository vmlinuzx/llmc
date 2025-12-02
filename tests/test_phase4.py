from tools.rag_nav.enrichment import EnrichmentSnippet
from tools.rag_nav.models import EnrichmentData, SearchItem, SearchResult, Snippet, SnippetLocation


def test_enrichment_data_structure():
    """Test that EnrichmentData supports the new content_type fields."""
    data = EnrichmentData(
        summary="Test summary",
        content_type="code",
        content_language="python"
    )
    d = data.to_dict()
    assert d["content_type"] == "code"
    assert d["content_language"] == "python"
    assert d["summary"] == "Test summary"

def test_enrichment_snippet_structure():
    """Test that EnrichmentSnippet dataclass has the new fields."""
    snip = EnrichmentSnippet(
        summary="Summary",
        content_type="docs",
        content_language="en"
    )
    assert snip.content_type == "docs"
    assert snip.content_language == "en"

def test_search_result_structure():
    """Test that SearchResult items can hold the new enrichment data."""
    enrich = EnrichmentData(content_type="code")
    item = SearchItem(
        file="foo.py", 
        snippet=Snippet("def foo(): pass", SnippetLocation("foo.py", 1, 1)),
        enrichment=enrich
    )
    res = SearchResult(query="foo", items=[item])
    d = res.to_dict()
    assert d["items"][0]["enrichment"]["content_type"] == "code"

# Mock SqliteEnrichmentStore to test fetch logic (without real DB)
class MockStore:
    def snippets_for_span_or_path(self, *args, **kwargs):
        return [EnrichmentSnippet(summary="sum", content_type="code", content_language="python")], "span"

def test_enrichment_attachment():
    """Test attaching enrichment to search result."""
    from tools.rag_nav.enrichment import attach_enrichments_to_search_result
    
    item = SearchItem(
        file="test.py",
        snippet=Snippet("code", SnippetLocation("test.py", 1, 1))
    )
    res = SearchResult(query="test", items=[item])
    
    # Manually call attachment with mock store
    store = MockStore()
    attach_enrichments_to_search_result(res, store)
    
    assert res.items[0].enrichment is not None
    assert res.items[0].enrichment["content_type"] == "code"
    assert res.items[0].enrichment["content_language"] == "python"
