#!/usr/bin/env python3
"""Smoke test for LLMC MCP server - tests stdio transport and tools."""

import asyncio
import json
from pathlib import Path
import sys

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llmc_mcp.config import load_config
from llmc_mcp.server import TOOLS, LlmcMcpServer


async def test_tools_list():
    """Test that tools are properly defined."""
    print("Testing tool definitions...")
    assert len(TOOLS) >= 3, f"Expected at least 3 tools, got {len(TOOLS)}"

    tool_names = {t.name for t in TOOLS}
    expected = {"rag_search", "read_file", "list_dir"}
    assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"

    print(f"  ✓ Found {len(TOOLS)} tools: {tool_names}")


async def test_config_load():
    """Test config loading."""
    print("Testing config loading...")
    config = load_config()

    assert config.enabled, "MCP should be enabled"
    assert config.config_version == "v0", f"Expected v0, got {config.config_version}"
    assert config.server.transport == "stdio", f"Expected stdio, got {config.server.transport}"

    print(f"  ✓ Config loaded: {config.config_version}, transport={config.server.transport}")


async def test_health_handler():
    """Test health check handler."""
    print("Testing health handler...")
    config = load_config()
    server = LlmcMcpServer(config)

    result = await server._handle_health()
    assert len(result) == 1, f"Expected 1 result, got {len(result)}"

    data = json.loads(result[0].text)
    assert data["ok"] is True, f"Health check failed: {data}"
    assert data["version"] == "v0", f"Wrong version: {data}"

    print(f"  ✓ Health response: ok={data['ok']}, version={data['version']}")


async def test_read_file_handler():
    """Test read_file handler."""
    print("Testing read_file handler...")
    config = load_config()
    server = LlmcMcpServer(config)

    # Read this test file itself
    result = await server._handle_read_file({"path": __file__})
    assert len(result) == 1

    data = json.loads(result[0].text)
    assert "data" in data, f"Expected data in response: {data}"
    assert "test_read_file_handler" in data["data"], "Should contain this function"

    print(f"  ✓ Read file: {data['meta']['path']} ({data['meta']['size']} bytes)")


async def test_read_file_security():
    """Test read_file rejects paths outside allowed roots."""
    print("Testing read_file security...")
    config = load_config()
    server = LlmcMcpServer(config)

    # Try to read /etc/passwd (should be blocked)
    result = await server._handle_read_file({"path": "/etc/passwd"})
    data = json.loads(result[0].text)

    assert "error" in data, f"Expected error for /etc/passwd: {data}"
    assert "outside allowed roots" in data["error"].lower() or "security" in data["error"].lower()

    print("  ✓ Security: blocked /etc/passwd access")


async def test_list_dir_handler():
    """Test list_dir handler."""
    print("Testing list_dir handler...")
    config = load_config()
    server = LlmcMcpServer(config)

    # List the llmc_mcp directory
    result = await server._handle_list_dir({"path": str(Path(__file__).parent)})
    data = json.loads(result[0].text)

    assert "data" in data, f"Expected data: {data}"
    assert isinstance(data["data"], list), "Expected list of entries"

    names = {e["name"] for e in data["data"]}
    assert "server.py" in names, f"Expected server.py in {names}"
    assert "config.py" in names, f"Expected config.py in {names}"

    print(f"  ✓ List dir: {data['meta']['returned_entries']} entries")


async def test_stat_handler():
    """Test stat handler."""
    print("Testing stat handler...")
    config = load_config()
    server = LlmcMcpServer(config)

    result = await server._handle_stat({"path": __file__})
    data = json.loads(result[0].text)

    assert "data" in data, f"Expected data: {data}"
    assert data["data"]["type"] == "file", f"Expected file type: {data}"
    assert data["data"]["size"] > 0, f"Expected non-zero size: {data}"

    print(f"  ✓ Stat: type={data['data']['type']}, size={data['data']['size']}")


async def main():
    """Run all smoke tests."""
    print("=" * 60)
    print("LLMC MCP Server Smoke Tests (M1)")
    print("=" * 60)

    try:
        await test_config_load()
        await test_tools_list()
        await test_read_file_handler()
        await test_read_file_security()
        await test_list_dir_handler()
        await test_stat_handler()

        print("=" * 60)
        print("✓ All smoke tests passed!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
