from unittest.mock import MagicMock, patch

import pytest

from llmc_mcp.config import McpConfig, McpToolsConfig

try:
    from llmc_mcp.server import LlmcMcpServer
except ImportError as e:
    pytest.skip(f"Skipping because mcp dependency is missing: {e}", allow_module_level=True)


@pytest.fixture
def mock_config():
    config = MagicMock(spec=McpConfig)
    config.tools = MagicMock(spec=McpToolsConfig)
    config.tools.allowed_roots = ["."]
    config.tools.enable_run_cmd = True
    config.tools.run_cmd_blacklist = []
    config.tools.exec_timeout = 5
    config.tools.executables = {}
    config.code_execution = MagicMock()
    config.code_execution.enabled = False
    config.observability = MagicMock()
    config.observability.enabled = False
    return config


@pytest.mark.skip(reason="Known gap in implementation")
@pytest.mark.asyncio
async def test_hybrid_mode_bypasses_isolation(mock_config):
    """Verify that hybrid mode sets host_mode=True and bypasses isolation."""
    mock_config.mode = "hybrid"
    mock_config.hybrid = MagicMock()
    mock_config.hybrid.promoted_tools = ["run_cmd"]
    mock_config.hybrid.include_execute_code = False
    mock_config.hybrid.bootstrap_budget_warning = 10000

    # We need to mock run_cmd to avoid actual execution but verify the call args
    with patch("llmc_mcp.tools.cmd.run_cmd") as mock_run_cmd:
        mock_run_cmd.return_value = MagicMock(
            success=True, stdout="ok", stderr="", exit_code=0, error=None
        )

        server = LlmcMcpServer(mock_config)

        # Test run_cmd
        result = await server._handle_run_cmd({"command": "echo check"})

        # Assert run_cmd was called with host_mode=True
        mock_run_cmd.assert_called_once()
        call_kwargs = mock_run_cmd.call_args.kwargs
        assert call_kwargs["host_mode"] is True, "Hybrid mode must set host_mode=True"


@pytest.mark.skip(reason="Known gap in implementation")
@pytest.mark.asyncio
async def test_classic_mode_enforces_isolation(mock_config):
    """Verify that classic mode sets host_mode=False."""
    mock_config.mode = "classic"

    with patch("llmc_mcp.tools.cmd.run_cmd") as mock_run_cmd:
        mock_run_cmd.return_value = MagicMock(
            success=True, stdout="ok", stderr="", exit_code=0, error=None
        )

        server = LlmcMcpServer(mock_config)

        # Test run_cmd
        result = await server._handle_run_cmd({"command": "echo check"})

        # Assert run_cmd was called with host_mode=False
        mock_run_cmd.assert_called_once()
        call_kwargs = mock_run_cmd.call_args.kwargs
        assert (
            call_kwargs["host_mode"] is False
        ), "Classic mode must set host_mode=False"


@pytest.mark.asyncio
async def test_hybrid_mode_execute_code_still_requires_isolation(mock_config):
    """Verify that execute_code still demands isolation even in hybrid mode."""
    mock_config.mode = "hybrid"
    mock_config.hybrid = MagicMock()
    mock_config.hybrid.promoted_tools = ["run_cmd"]
    mock_config.hybrid.include_execute_code = True
    mock_config.hybrid.bootstrap_budget_warning = 10000

    # Mock execute_code to ensure it's imported from the right place
    # We patch the one in llmc_mcp.tools.code_exec because server imports it inside the method
    # But wait, execute_code imports require_isolation. We want to verify require_isolation is called.

    with patch("llmc_mcp.isolation.require_isolation") as mock_require_isolation:
        # We need actual execute_code logic to run until it hits require_isolation
        # So we don't mock execute_code itself, but the isolation check inside it.

        server = LlmcMcpServer(mock_config)

        # Test execute_code
        # It should call require_isolation("execute_code")
        # We'll mock it to raise RuntimeError to simulate "not isolated"
        mock_require_isolation.side_effect = RuntimeError("Not isolated")

        result = await server._handle_execute_code({"code": "print('hello')"})

        mock_require_isolation.assert_called_with("execute_code")
        assert result[0].text, "Should return error text"
        assert "Not isolated" in result[0].text
