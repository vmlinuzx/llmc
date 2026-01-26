
from pathlib import Path
import sys

# Add the project root to the python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from llmc.rag_nav.tool_handlers import _read_snippet


def test_path_traversal_in_read_snippet():
    """
    Tests for VULN-001: Path Traversal in _read_snippet.
    """
    # The repo_root is the 'repo' directory inside the test directory.
    repo_root = Path(__file__).parent / "repo"
    
    # The path to the malicious graph.
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    
    # The path to the dummy passwd file we want to read.
    # The path traversal in the graph is relative to the repo_root.
    target_file_path = repo_root.parent / "passwd"

    # The malicious path from the graph.
    # This is the path that will be passed to _read_snippet.
    malicious_path = "../passwd"

    # Ensure the files exist before running the test
    assert repo_root.exists()
    assert graph_path.exists()
    assert target_file_path.exists()

    # Call the vulnerable function with the malicious path.
    # The 'path' argument to _read_snippet would be extracted from the graph in a real scenario.
    snippet = _read_snippet(str(repo_root), malicious_path, 1, 4)

    # Read the content of the target file.
    expected_content = target_file_path.read_text()

    # Assert that the snippet content is the content of the passwd file.
    assert snippet.text == expected_content, "The content of the snippet should be the content of the passwd file."

    print("VULN-001: Path traversal vulnerability in _read_snippet confirmed.")
    print(f"Successfully read: {target_file_path}")
    print(f"Content:\n{snippet.text}")

if __name__ == "__main__":
    test_path_traversal_in_read_snippet()
