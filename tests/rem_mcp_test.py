
import os
import asyncio
from pathlib import Path
import pytest
import json
from llmc_mcp.server import LlmcMcpServer
from llmc_mcp.config import load_config

@pytest.fixture
def mcp_server():
    os.environ["LLMC_ISOLATED"] = "1"
    config = load_config()
    # Disable isolation for testing
    config.isolation_mode = "disabled"
    config.tools.enable_run_cmd = True
    # Set allowed roots for fs tests
    config.tools.allowed_roots = ["/tmp", "/home/vmlinux/src/llmc"]
    server = LlmcMcpServer(config)
    yield server
    del os.environ["LLMC_ISOLATED"]

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_run_cmd_success(mcp_server):
    # Create a test file to be removed
    test_file = Path("/tmp/test_run_cmd_success.txt")
    test_file.touch()
    assert test_file.exists()

    args = {"command": f"rm {test_file}"}
    result = await mcp_server._handle_run_cmd(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert not test_file.exists()

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_run_cmd_fail(mcp_server):
    args = {"command": "ls /non_existent_dir"}
    result = await mcp_server._handle_run_cmd(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "exit_code" in data

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_run_cmd_empty(mcp_server):
    args = {"command": ""}
    result = await mcp_server._handle_run_cmd(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "error" in data
    assert "command is required" in data["error"]

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_run_cmd_timeout(mcp_server):
    args = {"command": "sleep 5", "timeout": 1}
    result = await mcp_server._handle_run_cmd(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "error" in data
    assert "Command timed out after 1s" in data["error"]

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_read_file_success(mcp_server):
    test_file = Path("/tmp/test_read_file_success.txt")
    test_content = "hello world"
    test_file.write_text(test_content)
    
    args = {"path": str(test_file)}
    result = await mcp_server._handle_read_file(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "data" in data
    assert data["data"] == test_content
    
    test_file.unlink()

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_read_file_not_found(mcp_server):
    args = {"path": "/tmp/non_existent_file.txt"}
    result = await mcp_server._handle_read_file(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "error" in data
    assert "File not found" in data["error"]

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_read_file_is_dir(mcp_server):
    args = {"path": "/tmp"}
    result = await mcp_server._handle_read_file(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "error" in data
    assert "Not a file" in data["error"]

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_read_file_outside_root(mcp_server):
    # Create a file outside the allowed root
    test_file = Path("/var/tmp/test_read_file_outside_root.txt")
    test_file.touch()

    args = {"path": str(test_file)}
    result = await mcp_server._handle_read_file(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "error" in data
    assert "is outside allowed roots" in data["error"]
    
    test_file.unlink()

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_list_dir_success(mcp_server):
    test_dir = Path("/tmp/test_list_dir_success")
    test_dir.mkdir(exist_ok=True)
    (test_dir / "file1.txt").touch()
    (test_dir / ".hidden_file").touch()
    
    args = {"path": str(test_dir)}
    result = await mcp_server._handle_list_dir(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "data" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["name"] == "file1.txt"
    
    # Test include_hidden
    args = {"path": str(test_dir), "include_hidden": True}
    result = await mcp_server._handle_list_dir(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "data" in data
    assert len(data["data"]) == 2
    
    (test_dir / "file1.txt").unlink()
    (test_dir / ".hidden_file").unlink()
    test_dir.rmdir()

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_stat_file_success(mcp_server):
    test_file = Path("/tmp/test_stat_file_success.txt")
    test_file.touch()
    
    args = {"path": str(test_file)}
    result = await mcp_server._handle_stat(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "data" in data
    assert data["data"]["type"] == "file"
    
    test_file.unlink()

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_fs_write_success(mcp_server):
    test_file = Path("/tmp/test_fs_write_success.txt")
    
    # Test writing a new file
    args = {"path": str(test_file), "content": "hello"}
    result = await mcp_server._handle_fs_write(args)
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "data" in data
    assert test_file.read_text() == "hello"
    
    # Test appending to the file
    args = {"path": str(test_file), "content": " world", "mode": "append"}
    result = await mcp_server._handle_fs_write(args)
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "data" in data
    assert test_file.read_text() == "hello world"

    test_file.unlink()

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_fs_mkdir_success(mcp_server):
    test_dir = Path("/tmp/test_fs_mkdir_success")
    
    args = {"path": str(test_dir)}
    result = await mcp_server._handle_fs_mkdir(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "data" in data
    assert test_dir.is_dir()
    
    test_dir.rmdir()

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_fs_move_success(mcp_server):
    src_file = Path("/tmp/src.txt")
    dest_file = Path("/tmp/dest.txt")
    src_file.touch()
    
    args = {"source": str(src_file), "dest": str(dest_file)}
    result = await mcp_server._handle_fs_move(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "data" in data
    assert not src_file.exists()
    assert dest_file.exists()
    
    dest_file.unlink()

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_fs_delete_file_success(mcp_server):
    test_file = Path("/tmp/test_fs_delete_file_success.txt")
    test_file.touch()
    
    args = {"path": str(test_file)}
    result = await mcp_server._handle_fs_delete(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "data" in data
    assert not test_file.exists()

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_fs_edit_success(mcp_server):
    test_file = Path("/tmp/test_fs_edit_success.txt")
    test_file.write_text("hello world")
    
    args = {"path": str(test_file), "old_text": "world", "new_text": "rem"}
    result = await mcp_server._handle_fs_edit(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert "data" in data
    assert test_file.read_text() == "hello rem"
    
    test_file.unlink()

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_execute_code_success(mcp_server):
    code = "print('hello from execute_code')"
    args = {"code": code}
    result = await mcp_server._handle_execute_code(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert "hello from execute_code" in data["stdout"]

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_execute_code_fail(mcp_server):
    code = "import sys; sys.exit(1)"
    args = {"code": code}
    result = await mcp_server._handle_execute_code(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "Process exited with code 1" in data["error"]

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_execute_code_timeout(mcp_server):
    mcp_server.config.code_execution.timeout = 1
    code = "import time; time.sleep(5)"
    args = {"code": code}
    result = await mcp_server._handle_execute_code(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert data["success"] is False
    assert "timed out" in data["error"]

@pytest.mark.allow_sleep
@pytest.mark.asyncio
async def test_execute_code_with_stubs(mcp_server):
    # The server in "classic" mode does not generate stubs by default.
    # We need to trigger stub generation manually for this test.
    from llmc_mcp.tools.code_exec import generate_stubs
    stubs_dir = Path(mcp_server.config.code_execution.stubs_dir)
    llmc_root = Path(mcp_server.config.tools.allowed_roots[1])
    generate_stubs(mcp_server.tools, stubs_dir, llmc_root)

    test_file = Path("/tmp/test_execute_code_with_stubs.txt")
    test_content = "content from stubs test"
    test_file.write_text(test_content)

    code = f"""
from stubs import read_file
result = read_file(path='{test_file}')
print(result['data'])
"""
    args = {"code": code}
    result = await mcp_server._handle_execute_code(args)
    
    assert result[0].text is not None
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert test_content in data["stdout"]

    test_file.unlink()
