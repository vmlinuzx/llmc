"""
RUTHLESS Test Suite for AST Chunker
Testing language coverage, structural boundaries, and robustness
"""

# Test files with known structure for validation
PYTHON_TEST_FILE = '''
# Test Python file
def function_one():
    """First function"""
    x = 1
    return x

class MyClass:
    """A test class"""

    def method_one(self):
        """First method"""
        return "hello"

    def method_two(self):
        """Second method"""
        return "world"

def function_two():
    """Second function"""
    y = 2
    return y
'''

SHELL_TEST_FILE = """
#!/bin/bash
# Test shell script

function_one() {
    echo "First function"
    return 0
}

class_two() {
    echo "Second function"
    ls -la
}

function_three() {
    echo "Third function"
}
"""

MARKDOWN_TEST_FILE = """
# Section One

This is content under section one.

## Subsection A

More content here.

# Section Two

Different content.

## Subsection B

Even more content.
"""


def test_ast_chunker_python():
    """Test AST chunker with Python file"""
    from scripts.rag.ast_chunker import ASTChunker

    chunker = ASTChunker()
    chunks = chunker.chunk_text(PYTHON_TEST_FILE, "test.py")

    print(f"Python chunks found: {len(chunks)}")
    for chunk_text, chunk_meta in chunks:
        print(f"  Chunk: {chunk_meta.get('span_type', 'unknown')} - {chunk_text[:50]}")

    assert len(chunks) > 0, "No chunks generated from Python file"
    assert any(
        "function_one" in chunk_text for chunk_text, _ in chunks
    ), "function_one not found in chunks"
    assert any(
        "MyClass" in chunk_text for chunk_text, _ in chunks
    ), "MyClass not found in chunks"


def test_ast_chunker_shell():
    """Test AST chunker with shell script"""
    from scripts.rag.ast_chunker import ASTChunker

    chunker = ASTChunker()
    chunks = chunker.chunk_text(SHELL_TEST_FILE, "test.sh")

    print(f"Shell chunks found: {len(chunks)}")
    for chunk_text, chunk_meta in chunks:
        print(f"  Chunk: {chunk_meta.get('span_type', 'unknown')} - {chunk_text[:50]}")

    assert len(chunks) > 0, "No chunks generated from shell script"


def test_ast_chunker_markdown():
    """Test AST chunker with markdown file"""
    from scripts.rag.ast_chunker import ASTChunker

    chunker = ASTChunker()
    chunks = chunker.chunk_text(MARKDOWN_TEST_FILE, "test.md")

    print(f"Markdown chunks found: {len(chunks)}")
    for chunk_text, chunk_meta in chunks:
        print(f"  Chunk: {chunk_meta.get('span_type', 'unknown')} - {chunk_text[:50]}")

    assert len(chunks) > 0, "No chunks generated from markdown file"
    assert any(
        "Section One" in chunk_text for chunk_text, _ in chunks
    ), "Section One not found in chunks"


def test_ast_chunker_syntax_error_robustness():
    """Test AST chunker handles syntax errors gracefully"""
    from scripts.rag.ast_chunker import ASTChunker

    bad_python = """
def function_one(
    # Missing closing parenthesis
    x = 1
    return x
"""

    chunker = ASTChunker()

    chunks = chunker.chunk_text(bad_python, "bad.py")
    print(f"Bad syntax chunks: {len(chunks)}")
    # Should not crash, might still produce chunks or fallback
    assert chunks is not None, "Chunker should not crash on syntax error"
