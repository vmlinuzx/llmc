import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from llmc_mcp.maasl import ResourceBusyError, ResourceDescriptor
from llmc_mcp.tools.fs import FsResult
from llmc_mcp.tools.fs_protected import (
    delete_file_protected,
    edit_block_protected,
    move_file_protected,
    write_file_protected,
)


class TestFsProtected(unittest.TestCase):
    def setUp(self):
        self.allowed_roots = ["/tmp/safe"]
        self.mock_maasl = MagicMock()
        self.mock_maasl_patcher = patch("llmc_mcp.tools.fs_protected.get_maasl", return_value=self.mock_maasl)
        self.mock_maasl_patcher.start()

        self.mock_validate_patcher = patch("llmc_mcp.tools.fs_protected.validate_path")
        self.mock_validate = self.mock_validate_patcher.start()
        # Default behavior: return the path passed in (as Path object)
        self.mock_validate.side_effect = lambda p, roots: Path(p)

        self.mock_write_patcher = patch("llmc_mcp.tools.fs_protected._write_file_unprotected")
        self.mock_write = self.mock_write_patcher.start()

        self.mock_edit_patcher = patch("llmc_mcp.tools.fs_protected._edit_block_unprotected")
        self.mock_edit = self.mock_edit_patcher.start()

        self.mock_move_patcher = patch("llmc_mcp.tools.fs_protected._move_file_unprotected")
        self.mock_move = self.mock_move_patcher.start()

        self.mock_delete_patcher = patch("llmc_mcp.tools.fs_protected._delete_file_unprotected")
        self.mock_delete = self.mock_delete_patcher.start()

    def tearDown(self):
        self.mock_maasl_patcher.stop()
        self.mock_validate_patcher.stop()
        self.mock_write_patcher.stop()
        self.mock_edit_patcher.stop()
        self.mock_move_patcher.stop()
        self.mock_delete_patcher.stop()

    def test_write_file_protected_success(self):
        # Setup
        expected_result = FsResult(success=True, data={"bytes_written": 100, "sha256": "hash"}, meta={})
        self.mock_maasl.call_with_stomp_guard.return_value = expected_result
        
        # Action
        result = write_file_protected(
            path="/tmp/safe/file.txt",
            allowed_roots=self.allowed_roots,
            content="content",
            agent_id="agent1"
        )

        # Assert
        self.assertEqual(result, expected_result)
        
        # Verify validate_path called
        self.mock_validate.assert_called_with("/tmp/safe/file.txt", self.allowed_roots)
        
        # Verify call_with_stomp_guard called correctly
        self.mock_maasl.call_with_stomp_guard.assert_called_once()
        args, kwargs = self.mock_maasl.call_with_stomp_guard.call_args
        
        self.assertEqual(kwargs["intent"], "write_file")
        self.assertEqual(kwargs["agent_id"], "agent1")
        self.assertEqual(len(kwargs["resources"]), 1)
        self.assertEqual(kwargs["resources"][0].identifier, "/tmp/safe/file.txt")
        self.assertEqual(kwargs["resources"][0].resource_class, "CRIT_CODE")

        # Execute the op passed to maasl and verify it calls the unprotected function
        op = kwargs["op"]
        op()
        self.mock_write.assert_called_with(
            path=Path("/tmp/safe/file.txt"),
            allowed_roots=self.allowed_roots,
            content="content",
            mode="rewrite",
            expected_sha256=None,
            max_bytes=10485760
        )

    def test_write_file_protected_path_validation_fail(self):
        # Setup
        self.mock_validate.side_effect = ValueError("Invalid path")

        # Action
        result = write_file_protected(
            path="/unsafe/file.txt",
            allowed_roots=self.allowed_roots,
            content="content"
        )

        # Assert
        self.assertFalse(result.success)
        self.assertIn("Path validation failed", result.error)
        self.mock_maasl.call_with_stomp_guard.assert_not_called()

    def test_write_file_protected_resource_busy(self):
        # Setup
        self.mock_maasl.call_with_stomp_guard.side_effect = ResourceBusyError(
            resource_key="key",
            holder_agent_id="other_agent",
            holder_session_id="other_session",
            wait_ms=100.0,
            max_wait_ms=1000
        )

        # Action
        result = write_file_protected(
            path="/tmp/safe/file.txt",
            allowed_roots=self.allowed_roots,
            content="content"
        )

        # Assert
        self.assertFalse(result.success)
        self.assertIn("File locked by other_agent", result.error)

    def test_move_file_protected_locks_both_paths(self):
        # Setup
        expected_result = FsResult(success=True, data={"source": "src", "dest": "dst"}, meta={})
        self.mock_maasl.call_with_stomp_guard.return_value = expected_result

        # Action
        result = move_file_protected(
            source="/tmp/safe/src.txt",
            dest="/tmp/safe/dst.txt",
            allowed_roots=self.allowed_roots
        )

        # Assert
        self.assertEqual(result, expected_result)
        
        self.mock_maasl.call_with_stomp_guard.assert_called_once()
        args, kwargs = self.mock_maasl.call_with_stomp_guard.call_args
        
        # Verify TWO resources are locked
        resources = kwargs["resources"]
        self.assertEqual(len(resources), 2)
        identifiers = sorted([r.identifier for r in resources])
        self.assertEqual(identifiers, ["/tmp/safe/dst.txt", "/tmp/safe/src.txt"])

        # Execute op
        op = kwargs["op"]
        op()
        self.mock_move.assert_called_with(
            source=Path("/tmp/safe/src.txt"),
            dest=Path("/tmp/safe/dst.txt"),
            allowed_roots=self.allowed_roots
        )

    def test_delete_file_protected_success(self):
        # Setup
        expected_result = FsResult(success=True, data={"deleted": "/tmp/safe/file.txt"}, meta={})
        self.mock_maasl.call_with_stomp_guard.return_value = expected_result

        # Action
        result = delete_file_protected(
            path="/tmp/safe/file.txt",
            allowed_roots=self.allowed_roots,
            recursive=True
        )

        # Assert
        self.assertEqual(result, expected_result)
        
        args, kwargs = self.mock_maasl.call_with_stomp_guard.call_args
        self.assertEqual(kwargs["intent"], "delete_file")
        
        op = kwargs["op"]
        op()
        self.mock_delete.assert_called_with(
            path=Path("/tmp/safe/file.txt"),
            allowed_roots=self.allowed_roots,
            recursive=True
        )

    def test_edit_block_protected_success(self):
        # Setup
        expected_result = FsResult(success=True, data={"replacements": 1}, meta={})
        self.mock_maasl.call_with_stomp_guard.return_value = expected_result

        # Action
        result = edit_block_protected(
            path="/tmp/safe/file.txt",
            allowed_roots=self.allowed_roots,
            old_text="old",
            new_text="new"
        )

        # Assert
        self.assertEqual(result, expected_result)
        
        args, kwargs = self.mock_maasl.call_with_stomp_guard.call_args
        self.assertEqual(kwargs["intent"], "edit_file")
        
        op = kwargs["op"]
        op()
        self.mock_edit.assert_called_with(
            path=Path("/tmp/safe/file.txt"),
            allowed_roots=self.allowed_roots,
            old_text="old",
            new_text="new",
            expected_replacements=1
        )
