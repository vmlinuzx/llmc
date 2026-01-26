
import asyncio
from llmc.rlm.sandbox.process_backend import ProcessSandboxBackend

async def test_permissive_import():
    sandbox = ProcessSandboxBackend(security_mode="permissive")
    sandbox.start()
    
    code = """
import os
os.system('echo PERMISSIVE_VULN > /tmp/rlm_permissive')
"""
    
    result = sandbox.execute(code)
    print(f"Success: {result.success}")
    
    if os.path.exists("/tmp/rlm_permissive"):
        print("PERMISSIVE IMPORT ESCAPE SUCCESSFUL!")
        os.remove("/tmp/rlm_permissive")
    else:
        print("Permissive import escape failed.")

if __name__ == "__main__":
    import os
    asyncio.run(test_permissive_import())
