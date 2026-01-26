
import pytest
from pathlib import Path
from unittest.mock import patch
from llmc_mcp.tools.rlm import mcp_rlm_query
from llmc_mcp.config import McpRlmConfig

@pytest.mark.asyncio
async def test_rlm_query_path_signature_explosion():
    """
    This test proves that mcp_rlm_query calls validate_path with invalid arguments.
    By using autospec=True, the mock will enforce the original function's signature.
    """
    config = McpRlmConfig(enabled=True)
    
    # We use autospec=True here to ensure the mock has the same signature as the real validate_path
    with patch("llmc_mcp.tools.rlm.validate_path", autospec=True) as mock_v:
        # This SHOULD fail because mcp_rlm_query passes repo_root and operation
        try:
            await mcp_rlm_query(
                {"task": "analyze", "path": "test.py"}, 
                config, 
                ["/repo"], 
                Path("/repo")
            )
        except TypeError as e:
            print(f"\nCaught expected signature explosion: {e}")
            return
            
    pytest.fail("mcp_rlm_query did not explode when calling validate_path with invalid arguments!")
