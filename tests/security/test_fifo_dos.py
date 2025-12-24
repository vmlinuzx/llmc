"""
Tests for DoS vulnerabilities.
"""

import os
import pytest
from pathlib import Path
import threading
import time

from llmc_mcp.tools.fs import write_file

# Timeout for async operations, in seconds
ASYNC_TIMEOUT = 2.0


class WriteThread(threading.Thread):
    """Helper thread to call write_file and store the result."""
    def __init__(self, path, content, allowed_roots):
        super().__init__()
        self.path = path
        self.content = content
        self.allowed_roots = allowed_roots
        self.result = None
        self.exception = None

    def run(self):
        try:
            self.result = write_file(
                self.path,
                self.allowed_roots,
                self.content,
                mode="append"
            )
        except Exception as e:
            self.exception = e


def test_write_file_append_fifo_dos(tmp_path: Path):
    """
    Verify that write_file in append mode does not block on a FIFO.
    This is a DoS vector.
    """
    fifo_path = tmp_path / "test_fifo"
    os.mkfifo(fifo_path)

    # allowed_roots needs to be a list of strings
    allowed_roots = [str(tmp_path)]

    thread = WriteThread(fifo_path, "some data", allowed_roots)
    thread.start()
    thread.join(timeout=ASYNC_TIMEOUT)

    # If the thread is still alive, it's blocked.
    if thread.is_alive():
        pytest.fail(f"write_file blocked on FIFO for more than {ASYNC_TIMEOUT}s")

    # If the thread finished, check that it failed gracefully
    assert thread.result is not None
    assert not thread.result.success
    assert "FIFO" in thread.result.error
