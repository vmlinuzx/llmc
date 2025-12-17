import os

from llmc.docgen.locks import DocgenLock


def test_lock_symlink_attack_prevention(tmp_path):
    """
    Ruthless test: Verify that DocgenLock does NOT truncate files if the lockfile
    is a symlink to a sensitive file.
    """
    # 1. Setup "sensitive" file
    sensitive_file = tmp_path / "sensitive_data.txt"
    original_content = "This is important data that must not be deleted."
    sensitive_file.write_text(original_content)

    # 2. Setup repo structure
    repo_root = tmp_path / "repo"
    llmc_dir = repo_root / ".llmc"
    llmc_dir.mkdir(parents=True)

    # 3. Create malicious symlink
    lock_path = llmc_dir / "docgen.lock"
    # relative symlink or absolute, both should be caught
    os.symlink(sensitive_file, lock_path)

    # 4. Attempt to acquire lock
    lock = DocgenLock(repo_root)
    acquired = lock.acquire()

    # 5. Verification
    # Should fail to acquire because it detects the symlink
    assert not acquired, "Lock should not be acquired if it's a symlink"

    # CRITICAL: Content should be preserved
    current_content = sensitive_file.read_text()
    assert (
        current_content == original_content
    ), "Sensitive file was truncated! VULNERABILITY FOUND!"


def test_lock_creation_no_truncate(tmp_path):
    """
    Verify that normal lock acquisition creates the file but doesn't truncate
    if it already exists (sanity check for the O_RDWR logic).
    """
    repo_root = tmp_path / "repo"
    llmc_dir = repo_root / ".llmc"
    llmc_dir.mkdir(parents=True)
    lock_path = llmc_dir / "docgen.lock"

    # Pre-create with content
    lock_path.write_text("existing state")

    lock = DocgenLock(repo_root)
    assert lock.acquire(), "Should acquire normal file"

    # Content should persist (or at least not be wiped empty immediately,
    # though the lock mechanism doesn't write to it, so it should remain)
    assert lock_path.read_text() == "existing state"

    lock.release()


def test_lock_race_condition_simulation(tmp_path):
    """
    Simulate a race where the file is created between check and open?
    Hard to do deterministically in python, but we can check the O_CREAT logic.
    """
    repo_root = tmp_path / "repo"
    lock = DocgenLock(repo_root)

    # File doesn't exist
    assert lock.acquire()
    assert (repo_root / ".llmc" / "docgen.lock").exists()
    lock.release()
