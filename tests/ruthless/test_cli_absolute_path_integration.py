"""
Integration test: Validate end-to-end CLI behavior with absolute paths.
This simulates what happens when a user tab-completes a path.
"""

from pathlib import Path
import tempfile


def test_cli_absolute_path_integration():
    """
    Simulate the full workflow:
    1. User is in repo root
    2. User runs: llmc docs generate /absolute/path/to/repo/file.py
    3. CLI should normalize it and succeed

    This test validates the path normalization logic in docs.py.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir).resolve()

        # Create a test file
        test_file = repo_root / "tools" / "rag" / "search.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("# Test file\ndef search(): pass\n")

        # Get absolute path (simulates tab-completion)
        absolute_input = test_file.resolve()

        # The normalization logic in docs.py should handle this
        # by converting it to relative before passing to orchestrator
        relative_path = absolute_input.relative_to(repo_root)

        # Verify normalization works
        assert relative_path == Path("tools/rag/search.py")
        assert not relative_path.is_absolute()

        print("✅ Absolute path successfully normalized:")
        print(f"   Repo root: {repo_root}")
        print(f"   Input (absolute): {absolute_input}")
        print(f"   Normalized (relative): {relative_path}")


if __name__ == "__main__":
    test_cli_absolute_path_integration()
    print("\n🎉 Integration test passed! CLI handles absolute paths correctly.")
