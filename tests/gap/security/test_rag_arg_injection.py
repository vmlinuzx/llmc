import asyncio
from pathlib import Path
import unittest
from unittest.mock import patch

import pytest

from llmc_agent.backends.llmc import LLMCBackend


class TestRAGArgInjection(unittest.TestCase):
    @pytest.mark.allow_network
    def test_search_arg_injection(self):
        """Test that search query is properly escaped to prevent argument injection."""

        # Mock repo root finding so we don't need real filesystem structure
        with patch(
            "llmc_agent.backends.llmc.LLMCBackend._find_repo_root",
            return_value=Path("/mock/repo"),
        ):
            backend = LLMCBackend(repo_root="/mock/repo")

            # Mock subprocess.run to capture arguments
            with patch("subprocess.run") as mock_run:
                # Mock return value to prevent crashes in result parsing
                # This makes the availability check pass (returncode 0)
                # And the search result parsing pass (valid empty JSON)
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = '{"results": []}'

                # Use a query that looks like a flag
                query = "-e --bad-flag"

                # Run the search (it's async)
                asyncio.run(backend.search(query))

                # Check calls to subprocess.run
                self.assertTrue(
                    mock_run.called, "subprocess.run should have been called"
                )

                found_search_call = False
                for call_args in mock_run.call_args_list:
                    args, _ = call_args
                    cmd_list = args[0]

                    # Check if this is a search command (contains the query)
                    if query in cmd_list:
                        found_search_call = True

                        # Find the index of the query
                        query_index = cmd_list.index(query)

                        # Assert that the element before query is '--'
                        # This assertion is expected to FAIL on the current codebase
                        if query_index > 0:
                            prev_arg = cmd_list[query_index - 1]
                            self.assertEqual(
                                prev_arg,
                                "--",
                                f"Query '{query}' was not preceded by '--'. Command was: {cmd_list}",
                            )
                        else:
                            self.fail(
                                f"Query '{query}' was the first argument? Command: {cmd_list}"
                            )

                if not found_search_call:
                    self.fail("No subprocess call found containing the query.")
