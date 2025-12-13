import os
import pytest
import threading
import time
from pathlib import Path
from llmc_mcp.tools.fs import write_file, read_file

@pytest.fixture
def tmp_fifo(tmp_path):
    fifo_path = tmp_path / "test.fifo"
    if hasattr(os, "mkfifo"):
        os.mkfifo(fifo_path)
        yield fifo_path
        if fifo_path.exists():
            os.unlink(fifo_path)
    else:
        pytest.skip("FIFOs not supported on this platform")

def test_read_file_blocks_fifo(tmp_fifo):
    """Verify read_file returns error for FIFO instead of blocking."""
    # We allow ample time, but expect immediate return
    allowed_roots = [str(tmp_fifo.parent)]
    
    # Run in thread to prevent test hang if it fails
    result_container = {}
    
    def target():
        result_container["result"] = read_file(str(tmp_fifo), allowed_roots)
        
    t = threading.Thread(target=target)
    t.start()
    t.join(timeout=2.0)
    
    if t.is_alive():
        pytest.fail("read_file hung on FIFO read! (Gap confirmed)")
        
    result = result_container["result"]
    assert result.success is False
    assert "Not a file" in result.error

def test_write_file_append_blocks_fifo(tmp_fifo):
    """Verify write_file (append) blocks on FIFO (Gap Confirmation)."""
    # This test is EXPECTED to fail (hang) if the gap exists.
    # So we want to assert that it DOES NOT hang.
    
    allowed_roots = [str(tmp_fifo.parent)]
    content = "test"
    mode = "append"
    
    result_container = {}
    
    def target():
        try:
            result_container["result"] = write_file(str(tmp_fifo), allowed_roots, content, mode=mode)
        except Exception as e:
            result_container["error"] = str(e)

    t = threading.Thread(target=target)
    t.start()
    t.join(timeout=2.0)
    
    if t.is_alive():
        # Ideally we kill the thread but in Python we can't easily.
        # We just report failure.
        pytest.fail("write_file hung on FIFO write! GAP CONFIRMED: write_file(append) allows opening FIFO.")
    
    # If it didn't hang, it must have failed gracefully
    if "result" in result_container:
        result = result_container["result"]
        # If it succeeded, that's weird for a FIFO with no reader (should block or fail)
        # If it returned error, good.
        assert result.success is False, f"write_file succeeded on FIFO? {result}"
