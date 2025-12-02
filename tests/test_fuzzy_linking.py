import textwrap

# We will create tools.rag.locator later
try:
    from tools.rag.locator import identify_symbol_at_line
except ImportError:
    pass


class TestFuzzyLinking:
    def test_identify_simple_function(self):
        source = textwrap.dedent("""
        def foo():
            print("hello")
            return 1
        """).strip()
        # Line 1: def foo():
        symbol = identify_symbol_at_line(source, 1)
        assert symbol == "foo"

        # Line 3: return 1
        symbol = identify_symbol_at_line(source, 3)
        assert symbol == "foo"

    def test_identify_class_method(self):
        source = textwrap.dedent("""
        class MyClass:
            def method(self):
                pass
        """).strip()
        # Line 1: class
        symbol = identify_symbol_at_line(source, 1)
        assert symbol == "MyClass"

        # Line 2: def method
        symbol = identify_symbol_at_line(source, 2)
        assert symbol == "MyClass.method"

    def test_identify_module_level(self):
        source = textwrap.dedent("""
        import os
        
        x = 1
        """).strip()
        # Line 3: x = 1 (outside any def)
        symbol = identify_symbol_at_line(source, 3)
        # Should return None or special module indicator?
        # SDD says "Optional[str]", so None implies "Module Scope" or "No Symbol"
        assert symbol is None

    def test_identify_nested_function(self):
        source = textwrap.dedent("""
        def outer():
            def inner():
                pass
        """).strip()
        symbol = identify_symbol_at_line(source, 2)
        assert symbol == "outer.inner"

    def test_resilient_matching_integration_logic(self):
        """
        Simulates the tool handler logic:
        1. Have a graph node with OLD line numbers but Valid ID.
        2. Have a file with NEW line numbers.
        3. Resolve line -> ID -> Node.
        """
        # Mock Graph Node (Old state)
        # Graph thinks 'login' is at line 10
        graph_node = {"id": "auth.login", "metadata": {"summary": "Authenticates"}}
        graph_index = {"auth.login": graph_node}

        # Real File (New state)
        # 'login' is actually at line 20 because we added comments
        source = "\n" * 19 + "def login(): pass"

        # We have a search hit at line 20
        hit_line = 20

        # Action: Identify symbol at line 20
        symbol_id = identify_symbol_at_line(source, hit_line)

        # Expectation: We find "login" (or "auth.login" if we provided context,
        # but unit test just parses string so it sees "login")
        assert symbol_id == "login"

        # Then we construct the full ID (in the handler)
        full_id = f"auth.{symbol_id}"

        # And find the node
        found = graph_index.get(full_id)
        assert found is not None
        assert found["metadata"]["summary"] == "Authenticates"
