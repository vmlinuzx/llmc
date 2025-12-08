
import os
import unittest
from unittest.mock import MagicMock, patch

from llmc_mcp.isolation import is_isolated_environment
from llmc_mcp.tools.cmd import run_cmd


class TestRunCmdIsolation(unittest.TestCase):
    def setUp(self):
        # Clear the cache before each test to ensure fresh environment detection
        is_isolated_environment.cache_clear()

    def tearDown(self):
        is_isolated_environment.cache_clear()

    def test_run_cmd_fails_without_isolation(self):
        """Test that run_cmd fails when no isolation markers are present."""
        # Ensure environment is clean of isolation markers
        with patch.dict(os.environ, {}, clear=True):
            # Mock Path.exists to always return False for isolation checks
            with patch("llmc_mcp.isolation.Path.exists", return_value=False):
                 # Also need to mock /proc/1/cgroup reading to not trigger actual read or fail
                with patch("llmc_mcp.isolation.Path.read_text", side_effect=OSError):
                    result = run_cmd("echo 'test'", cwd="/tmp")
        
        self.assertFalse(result.success)
        self.assertIn("SECURITY: Tool 'run_cmd' requires an isolated environment", result.error)
        self.assertEqual(result.exit_code, -1)

    def test_run_cmd_succeeds_with_env_var(self):
        """Test that run_cmd passes check when LLMC_ISOLATED=1 is set."""
        # Mock subprocess.run to avoid actual execution, just verify we got past the check
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "mocked output"
            mock_run.return_value.stderr = ""
            
            with patch.dict(os.environ, {"LLMC_ISOLATED": "1"}):
                result = run_cmd("echo 'test'", cwd="/tmp")

        self.assertTrue(result.success)
        self.assertEqual(result.stdout, "mocked output")

    def test_run_cmd_succeeds_with_docker_marker(self):
        """Test that run_cmd passes check when /.dockerenv exists."""
        # Mock subprocess.run
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "docker output"
            mock_run.return_value.stderr = ""
            
            # Ensure no env var isolation
            with patch.dict(os.environ, {}, clear=True):
                # Mock Path to simulate .dockerenv existence
                # We need to be careful to only return True for .dockerenv if we can,
                # or just True generally if it doesn't break other things.
                # Since is_isolated_environment creates Path("/.dockerenv"), we can patch Path in that module.
                
                # However, run_cmd ALSO uses Path for cwd resolution.
                # So simply returning True for all exists() might be confusing but acceptable if we control the flow.
                # Better to use a side_effect.
                
                def exists_side_effect(self):
                    if str(self) == "/.dockerenv":
                        return True
                    return False # Default to False for other isolation checks
                
                # We need to patch Path in llmc_mcp.isolation.
                # But is_isolated_environment instantiates Path("/.dockerenv").
                # So we patch llmc_mcp.isolation.Path.
                
                # Note: run_cmd uses Path(cwd).resolve().
                # If we only patch llmc_mcp.isolation.Path, run_cmd's Path shouldn't be affected 
                # UNLESS they refer to the same object (which they likely do if it's the class).
                # But patching 'llmc_mcp.isolation.Path' replaces the name in that module.
                
                with patch("llmc_mcp.isolation.Path") as MockPathIsolation:
                    # Setup the mock instance
                    mock_path_instance = MockPathIsolation.return_value
                    # Setup exists return value
                    mock_path_instance.exists.return_value = True
                    
                    # We need to make sure the Logic in is_isolated_environment:
                    # Path("/.dockerenv").exists() -> True
                    
                    # Since we are mocking the class constructor, MockPathIsolation("/.dockerenv") returns a mock.
                    # We want that mock's .exists() to return True.
                    
                    # But wait, we need to distinguish between /.dockerenv and /proc/1/cgroup.
                    # It's easier if we can control it based on init args.
                    
                    def mock_path_constructor(path_str):
                        m = MagicMock()
                        if path_str == "/.dockerenv":
                            m.exists.return_value = True
                        else:
                            m.exists.return_value = False
                            m.read_text.side_effect = OSError
                        return m
                    
                    MockPathIsolation.side_effect = mock_path_constructor
                    
                    # We also need to ensure run_cmd works. 
                    # run_cmd does: cwd_path = Path(cwd).resolve()
                    # It imports Path from pathlib. 
                    # If we don't patch llmc_mcp.tools.cmd.Path, it uses real Path.
                    # This is fine. We only want to trick is_isolated_environment.
                    
                    result = run_cmd("echo 'test'", cwd="/tmp")

        self.assertTrue(result.success)
        self.assertEqual(result.stdout, "docker output")

