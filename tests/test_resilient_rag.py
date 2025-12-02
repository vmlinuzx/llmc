import json

from tools.rag_nav.models import SearchItem, Snippet, SnippetLocation
from tools.rag_nav.tool_handlers import _attach_graph_enrichment


class TestResilientRag:
    
    def test_enrichment_survives_line_drift(self, tmp_path):
        """
        Test that enrichment is attached even if the file on disk has
        different line numbers than the graph, thanks to AST linking.
        """
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".llmc").mkdir()
        
        # 1. Setup Graph (OLD State)
        # Graph says 'login' is at lines 10-20
        graph_nodes = [
            {
                "id": "sym:auth.login",
                "path": "src/auth.py",
                "span": {"start_line": 10, "end_line": 20},
                "metadata": {"summary": "Found me!"}
            }
        ]
        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.write_text(json.dumps({"nodes": graph_nodes, "edges": []}))
        
        # 2. Setup File (NEW State)
        # We inserted 100 lines of comments at the top.
        # 'login' is now at line 110.
        file_path = repo_root / "src" / "auth.py"
        file_path.parent.mkdir()
        
        new_content = ("# comment\n" * 100) + "def login():\n    pass"
        file_path.write_text(new_content)
        
        # 3. Setup Search Result (from grep/FTS)
        # Search found the function at the NEW location (line 111)
        # Note: line 111 because 100 lines of comments + 1 line of def
        item = SearchItem(
            file="src/auth.py",
            snippet=Snippet(
                text="def login():",
                location=SnippetLocation(path="src/auth.py", start_line=101, end_line=102)
            )
        )
        
        # 4. Run Enrichment Attachment
        # It should parse the file, find 'login' at 101, construct ID 'auth.login',
        # match it to graph node 'sym:auth.login', and attach metadata.
        items = _attach_graph_enrichment(repo_root, [item])
        
        # 5. Assert
        assert len(items) == 1
        assert items[0].enrichment is not None
        assert items[0].enrichment.summary == "Found me!"

