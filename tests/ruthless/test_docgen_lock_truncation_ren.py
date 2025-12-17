import os

import pytest

from llmc.docgen.locks import DocgenLock


class TestLockTruncationRen:
    """Ruthless testing for lock file truncation vulnerability."""

    @pytest.fixture
    def repo_root(self, tmp_path):
        (tmp_path / ".llmc").mkdir()
        return tmp_path

    def test_lock_blocks_symlink_attack(self, repo_root):
        """Test that lock BLOCKS symlink attacks (Security Fix Verification)."""
        # 1. Create a "valuable" file
        target_file = repo_root / "valuable_data.txt"
        original_content = "This data should not be lost."
        target_file.write_text(original_content)

        # 2. Create a symlink from lock file to valuable file (ATTACK)
        lock_file = repo_root / ".llmc" / "docgen.lock"
        try:
            os.symlink(target_file, lock_file)
        except OSError:
            pytest.skip("Cannot create symlinks")

        # 3. Try to acquire lock - should FAIL due to symlink detection
        lock = DocgenLock(repo_root)

        # The security fix should prevent acquiring lock on symlinks
        acquired = lock.acquire()
        assert acquired is False, "Lock should refuse symlinked files"

        # 4. Verify target file content is preserved (wasn't even opened)
        new_content = target_file.read_text()
        assert new_content == original_content, "Target file should be untouched"

    def test_lock_no_truncation_normal_file(self, repo_root):
        """Test that normal lock files are NOT truncated (Security Fix Verification)."""
        lock_file = repo_root / ".llmc" / "docgen.lock"
        original_content = "PID: 12345"
        lock_file.write_text(original_content)

        lock = DocgenLock(repo_root)
        acquired = lock.acquire()
        assert acquired is True
        lock.release()

        # Content should be preserved (no truncation)
        content = lock_file.read_text()
        assert content == original_content, "Lock file should not be truncated"
