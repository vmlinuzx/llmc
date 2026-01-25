from llmc_mcp.config import McpConfig

def test_rlm_config_defaults():
    config = McpConfig()
    assert config.rlm.enabled is False
    assert config.rlm.max_loops == 5
    assert config.rlm.timeout == 300
