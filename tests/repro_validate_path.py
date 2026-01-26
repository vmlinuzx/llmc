import asyncio
from pathlib import Path
from llmc_mcp.config import McpRlmConfig
from llmc_mcp.tools.rlm import mcp_rlm_query
import pytest

@pytest.mark.asyncio
async def test_validate_path_signature_mismatch():
    config = McpRlmConfig(enabled=True, allow_path=True)
    allowed_roots = ["/tmp"]
    repo_root = Path("/tmp")
    
    # This should fail with TypeError because validate_path doesn't take repo_root or operation
    args = {
        "task": "test",
        "path": "/tmp/test.txt"
    }
    
    # Create the file so it exists
    test_file = repo_root / "test.txt"
    test_file.write_text("content")
    
    try:
        await mcp_rlm_query(args, config, allowed_roots, repo_root)
    except TypeError as e:
        print(f"\nCaught expected TypeError: {e}")
        assert "unexpected keyword argument" in str(e)
    else:
        pytest.fail("Should have raised TypeError due to signature mismatch")

if __name__ == "__main__":
    asyncio.run(test_validate_path_signature_mismatch())
