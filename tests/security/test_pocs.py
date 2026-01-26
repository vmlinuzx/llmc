from pathlib import Path
from unittest.mock import patch

import pytest

# --- POC 1: TE Command Injection ---
from llmc.te.cli import _handle_passthrough


def test_poc_te_command_injection():
    """
    Security Verification: TE CLI does NOT use shell=True.

    Originally a PoC showing shell=True vulnerability.
    Now verifies the fix: shell=False prevents command injection.
    """
    print("\n[+] Testing TE Command Injection Prevention...")

    with patch("llmc_agent.backends.llmc.subprocess.run") as mock_run:
        # Simulate 'te run "; echo pwned"'
        command = "run"
        args = ["; echo pwned"]
        repo_root = Path("/tmp")

        _handle_passthrough(command, args, repo_root)

        # Check what was passed to subprocess
        assert mock_run.called
        call_args = mock_run.call_args
        cmd_arg = call_args[0][0]  # The first positional arg is the command
        shell_arg = call_args[1].get("shell")

        print(f"Executed command: {cmd_arg!r}")
        print(f"Shell argument: {shell_arg}")

        # Verify shell=False (vulnerability is fixed)
        assert shell_arg is not True, \
            "SECURITY REGRESSION: shell=True is still being used!"
        
        print("[+] SECURITY VERIFIED: shell=False prevents injection.")


# --- POC 2: LLMC Backend Flag Injection ---
from llmc_agent.backends.llmc import LLMCBackend


@pytest.mark.asyncio
async def test_poc_llmc_flag_injection():
    """
    POC: Flag Injection in LLMC Backend.

    The backend passes the query directly to subprocess without '--'.
    A query starting with '-' is interpreted as a flag.
    """
    print("\n[+] Testing LLMC Backend Flag Injection...")

    backend = LLMCBackend(repo_root=Path("."))

    # Mock _check_llmc_available to force fallback search (rg)
    backend._llmc_available = False  # Force fallback to rg

    with patch("llmc_agent.backends.llmc.subprocess.run") as mock_run:
        # Simulate searching for a flag-like string
        query = "--help"

        await backend._fallback_search(query, limit=5)

        assert mock_run.called
        call_args = mock_run.call_args[0][0]  # The command list

        print(f"Subprocess call: {call_args}")

        # Check if query is treated as a positional arg or if it might be a flag
        # If the command is ['rg', ..., '--help'], rg prints help instead of searching.
        if "--" not in call_args and query in call_args:
            print("[!] VULNERABILITY CONFIRMED: Query passed without '--' delimiter.")
        else:
            print("[-] Mitigation found: '--' delimiter present.")


# --- POC 3: RUTA Safe Eval Bypass (DoS) ---
from llmc.ruta.judge import _safe_eval


def test_poc_ruta_safe_eval_dos():
    """
    POC: Denial of Service in RUTA _safe_eval.

    simpleeval prevents code execution but might not prevent resource exhaustion.
    Exponential string creation: "a" * 10**9
    """
    print("\n[+] Testing RUTA Safe Eval DoS...")

    # Simpleeval usually blocks '10**9' if safety limits are set, but let's check.
    # We'll try a smaller but significant multiplier to show the risk without crashing this test runner.
    payload = "'a' * 1000000"

    try:
        context = {}
        result = _safe_eval(payload, context)
        if len(result) == 1000000:
            print(
                f"[!] VULNERABILITY CONFIRMED: Resource exhaustion possible (created {len(result)} chars)."
            )
        else:
            print("[-] Payload failed to execute as expected.")
    except Exception as e:
        print(f"[-] Evaluation failed (Good): {e}")


if __name__ == "__main__":
    # Manually run tests if executed as script
    try:
        test_poc_te_command_injection()
        import asyncio

        asyncio.run(test_poc_llmc_flag_injection())
        test_poc_ruta_safe_eval_dos()
        print("\n[+] All POCs finished.")
    except Exception as e:
        print(f"\n[!] An error occurred: {e}")
