import asyncio
from unittest.mock import patch

import pytest

from llmc_agent.backends.llmc import LLMCBackend


def test_llmc_backend_injection_sync():
    """Verify that user queries starting with - are treated as flags without -- delimiter."""

    async def run_test():
        from pathlib import Path

        repo_root = Path(__file__).parent.parent.parent
        print(f"Repo root: {repo_root}")

        backend = LLMCBackend(repo_root=repo_root)

        # We mock subprocess.run to capture arguments
        with patch("subprocess.run") as mock_run:
            # Configure mock to look like success
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = '{"results": []}'

            # Attack query
            attack_query = "--help"

            await backend.search(attack_query)

            print(f"Mock calls: {mock_run.call_args_list}")

            if not mock_run.call_args:
                pytest.fail(
                    f"subprocess.run was not called. Repo root found? {backend.repo_root}"
                )

            # Check what was passed
            args, _ = mock_run.call_args
            cmd_list = args[0]

            # If safe, it should be [..., "search", "--", "--help", ...]
            # If unsafe, it is [..., "search", "--help", ...]

            # We expect it to be UNSAFE currently based on code review
            # We search for the index of "search"
            try:
                search_idx = cmd_list.index("search")
                # The next arg should be the query
                next_arg = cmd_list[search_idx + 1]

                if next_arg == "--":
                    pytest.fail("Vulnerability NOT found: '--' delimiter is present.")
                elif next_arg == attack_query:
                    # Vulnerability confirmed
                    pass
                else:
                    # Maybe arguments are shifted?
                    pass
            except ValueError:
                pass

    asyncio.run(run_test())
