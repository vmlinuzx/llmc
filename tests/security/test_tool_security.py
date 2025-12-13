
import pytest
from pathlib import Path
from llmc_mcp.tools.fs import check_path_allowed, validate_path, PathSecurityError
from llmc_agent.tools import detect_intent_tier, ToolTier

def test_path_traversal_blocked():
    """Verify that accessing files outside allowed roots is blocked."""
    cwd = Path.cwd().resolve()
    allowed_roots = [str(cwd)]
    
    # Try to access parent directory
    parent_file = cwd.parent / "sensitive_file"
    
    # Check directly
    assert check_path_allowed(parent_file, allowed_roots) is False
    
    # Check via validate_path
    with pytest.raises(PathSecurityError, match="outside allowed roots"):
        validate_path("../sensitive_file", allowed_roots)

def test_symlink_escape_blocked(tmp_path):
    """Verify that following symlinks to outside allowed roots is blocked."""
    # Create a sensitive file outside the allowed root
    sensitive_dir = tmp_path / "sensitive"
    sensitive_dir.mkdir()
    secret_file = sensitive_dir / "secret.txt"
    secret_file.write_text("top secret")
    
    # Create an allowed root
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()
    
    # Create a symlink in allowed dir pointing to secret file
    symlink = allowed_dir / "link_to_secret"
    symlink.symlink_to(secret_file)
    
    # Attempt to access via symlink
    allowed_roots = [str(allowed_dir)]
    
    with pytest.raises(PathSecurityError, match="Symlink escapes allowed roots"):
        validate_path(str(symlink), allowed_roots)

def test_empty_allowed_roots_is_full_access():
    """Verify that empty allowed_roots list grants full access (Dangerous Default)."""
    # This documents the insecure default behavior
    assert check_path_allowed(Path("/etc/passwd"), []) is True

def test_intent_tier_bypass():
    """Verify how easy it is to trigger tool tier escalation."""
    # Benign-looking prompt that shouldn't need write access
    prompt = "I read the logs and found a fix-it ticket number."
    
    # Logic sees "fix" and escalates to RUN (Write access)
    tier = detect_intent_tier(prompt)
    assert tier == ToolTier.RUN

def test_intent_tier_default_is_walk():
    """Verify that default tier allows reading files."""
    # Even with a prompt that has no keywords
    prompt = "Hello there."
    tier = detect_intent_tier(prompt)
    
    # It defaults to CRAWL in the function, BUT ToolRegistry defaults to WALK
    # The function returns the DETECTED intent, not the BASE level.
    assert tier == ToolTier.CRAWL

