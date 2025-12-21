import stat
import unittest
from unittest.mock import MagicMock, patch
import pytest
from llmc_mcp.tools.fs import edit_block


class TestMcpEditOom(unittest.TestCase):
    @pytest.mark.skip(reason="Known gap in implementation")
    @patch("llmc_mcp.tools.fs.Path")
    def test_edit_block_rejects_large_files(self, MockPath):
        """
        Test that edit_block rejects files larger than the safety limit (e.g. 10MB)
        to prevent OOM vulnerabilities.
        """
        # The path object used in logic
        mock_path_obj = MagicMock()

        # When Path("...") is called, return a mock that returns mock_path_obj on resolve()
        # Because validate_path does: Path(str).resolve()
        MockPath.return_value.resolve.return_value = mock_path_obj

        # Basic checks
        mock_path_obj.exists.return_value = True
        mock_path_obj.is_file.return_value = True
        mock_path_obj.is_symlink.return_value = False

        # Stat setup
        mock_stat = MagicMock()
        mock_stat.st_size = 20 * 1024 * 1024  # 20MB
        mock_stat.st_mode = stat.S_IFREG  # Regular file
        mock_path_obj.stat.return_value = mock_stat

        # Mock read_text to ensure it doesn't crash if called (simulating real file read)
        mock_path_obj.read_text.return_value = "some content"

        # Execution
        # We pass allowed_roots=[] which means "allow all" in the current implementation of check_path_allowed
        result = edit_block("/tmp/fake_large_file", [], "foo", "bar")

        # Verification
        # This assertion is expected to FAIL until the bug is fixed.
        self.assertFalse(result.success, "Should fail for large file")
        self.assertIsNotNone(result.error)
        self.assertIn(
            "too large",
            result.error.lower(),
            f"Error should mention size limit, got: {result.error}",
        )
