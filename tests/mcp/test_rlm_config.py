# from pydantic import ValidationError
import pytest

from llmc_mcp.config import McpConfig


def test_rlm_config_defaults():
    config = McpConfig()
    # Should exist and have defaults
    assert config.rlm is not None
    assert config.rlm.enabled is False
    assert config.rlm.default_timeout_s == 300
    # Check default profile is unrestricted as per code
    assert config.rlm.profile == "unrestricted"
    
    # Check default defaults
    assert config.rlm.default_max_bytes == 262144
    assert config.rlm.default_max_turns == 5

@pytest.mark.parametrize("rlm_params", [
    {"enabled": "true"},
    {"provider": 123},
    {"models": "model-name"},
    {"tools": {"tool": "a"}},
])
def test_invalid_rlm_config_raises_validation_error(rlm_params):
    config = {"rlm": rlm_params}
    with pytest.raises(ValueError):
        McpConfig(**config)
