
import pytest
from pathlib import Path
from llmc.docgen.gating import resolve_doc_path

def test_resolve_doc_path_traversal():
    repo_root = Path("/tmp/fake_repo")
    
    # Test 1: Simple traversal
    with pytest.raises(ValueError, match="Path traversal detected"):
        resolve_doc_path(repo_root, Path("../../etc/passwd"))

    # Test 2: Absolute path attempt (should be treated as relative or fail if joined)
    # If joined, /tmp/fake_repo + /etc/passwd = /etc/passwd (on some systems) or /tmp/fake_repo/etc/passwd
    # pathlib.Path.joinpath with absolute path ignores previous parts.
    # Let's see how resolve_doc_path handles it.
    # It does: output_base / f"{relative_path}.md"
    # if relative_path is absolute, output_base is ignored! 
    # This is a classic pitfall. Let's see if the security check catches it.
    
    try:
        resolve_doc_path(repo_root, Path("/etc/passwd"))
    except ValueError as e:
        assert "Path traversal detected" in str(e)
    except Exception as e:
        # If it raises something else or succeeds, we need to know
        pytest.fail(f"Unexpected result for absolute path: {e}")

    # Test 3: Deep traversal
    with pytest.raises(ValueError, match="Path traversal detected"):
        resolve_doc_path(repo_root, Path("foo/../../../../etc/passwd"))

    # Test 4: Valid path
    try:
        p = resolve_doc_path(repo_root, Path("llmc/main.py"))
        assert str(p).endswith("DOCS/REPODOCS/llmc/main.py.md")
    except Exception as e:
        pytest.fail(f"Valid path failed: {e}")

def test_resolve_doc_path_symlink_attack(tmp_path):
    # Setup a real filesystem scenario
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    output_dir = repo_root / "DOCS" / "REPODOCS"
    output_dir.mkdir(parents=True)
    
    # Create a symlink inside output_dir that points outside
    # Wait, resolve_doc_path resolves the OUTPUT path. 
    # If I ask for "evil_link", and "evil_link.md" exists and is a symlink to /etc/passwd...
    # The function creates the path object, it doesn't write to it yet.
    # But resolve() on a path that doesn't exist ... depends on python version.
    # Python 3.10+ resolve() is strict=False by default (resolves symlinks even if file doesn't exist? No, it resolves '.' and '..')
    # Actually, if the file doesn't exist, resolve() still normalizes '..'.
    # BUT it doesn't follow symlinks if they don't exist.
    # If the file DOES exist and is a symlink, resolve() follows it.
    
    # Attack scenario:
    # 1. Attacker creates a symlink 'DOCS/REPODOCS/innocent.py.md' -> '/etc/passwd'
    # 2. Attacker runs docgen for 'innocent.py'
    # 3. docgen writes to the resolved path... which is /etc/passwd!
    
    evil_link = output_dir / "innocent.py.md"
    target = tmp_path / "secret.txt"
    target.write_text("secret")
    
    evil_link.symlink_to(target)
    
    # Now try to resolve 'innocent.py'
    # strict=False is default for Path.resolve() in newer python, checking what version we have.
    # The code uses doc_path_candidate.resolve()
    
    try:
        resolved = resolve_doc_path(repo_root, Path("innocent.py"))
        # If resolved points to target, then we have a problem IF target is outside output_dir.
        # target IS outside output_dir.
        
        # The security check: doc_path_resolved.relative_to(output_base)
        # If resolved is /tmp/.../secret.txt, and output_base is /tmp/.../repo/DOCS/REPODOCS
        # relative_to should FAIL.
        
        print(f"Resolved: {resolved}")
        print(f"Output base: {output_dir.resolve()}")
        
        # This assertion expects the security check to catch it
        # If it didn't raise ValueError, we failed to block the attack
        pytest.fail(f"Symlink attack succeeded! Resolved to: {resolved}")
        
    except ValueError as e:
        assert "Path traversal detected" in str(e)

