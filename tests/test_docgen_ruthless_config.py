from llmc.docgen.backends.shell import load_shell_backend


def test_load_shell_backend_allows_path_traversal(tmp_path):
    """Verify that load_shell_backend allows executing scripts outside the repo."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Create a script OUTSIDE the repo
    outside_script = tmp_path / "evil_script.sh"
    outside_script.write_text("#!/bin/sh\necho 'owned'")
    outside_script.chmod(0o755)

    # Config pointing to the outside script using ..
    config = {"shell": {"script": "../evil_script.sh", "timeout_seconds": 10}}

    # This should succeed (but ideally shouldn't)
    backend = load_shell_backend(repo_root, config)

    # Verify it resolved to the outside script
    assert backend.script.resolve() == outside_script.resolve()
    assert not str(backend.script.resolve()).startswith(str(repo_root.resolve()))
