
from pathlib import Path
import sys

import pytest

from llmc.docgen.backends.shell import ShellDocgenBackend


# Fixture to create a dummy script
@pytest.fixture
def echo_script(tmp_path):
    script_path = tmp_path / "echo_script.py"
    script_content = """
import sys
import json

input_data = sys.stdin.read()
data = json.loads(input_data)
print(f"SHA256: {data['file_sha256']}")
print(f"# Doc for {data['relative_path']}")
"""
    script_path.write_text(script_content)
    return script_path

@pytest.fixture
def hang_script(tmp_path):
    script_path = tmp_path / "hang_script.py"
    script_content = """
import time
import sys
# Read stdin to ensure we don't block caller
sys.stdin.read()
time.sleep(2)
"""
    script_path.write_text(script_content)
    return script_path

@pytest.fixture
def garbage_script(tmp_path):
    script_path = tmp_path / "garbage_script.py"
    script_content = """
print("I am not a valid docgen output")
"""
    script_path.write_text(script_content)
    return script_path

def test_shell_backend_happy_path(echo_script, tmp_path):
    backend = ShellDocgenBackend(
        script=echo_script,
        args=["python3"], # This is wrong, args are appended to script path? 
                          # Wait, the code says: cmd = [str(self.script)] + self.args
                          # So if script is "echo_script.py", it tries to exec it directly.
                          # It needs to be executable or we need to pass "python3" as script and script path as arg.
        timeout_seconds=5
    )
    # Re-reading code: cmd = [str(self.script)] + self.args
    # If I pass script=Path("python3"), args=[str(echo_script)]
    
    backend = ShellDocgenBackend(
        script=Path(sys.executable),
        args=[str(echo_script)],
        timeout_seconds=5
    )

    result = backend.generate_for_file(
        repo_root=tmp_path,
        relative_path=Path("foo.py"),
        file_sha256="deadbeef",
        source_contents="print('hello')",
        existing_doc_contents=None,
        graph_context=None
    )

    assert result.status == "generated"
    assert result.sha256 == "deadbeef"
    assert "# Doc for foo.py" in result.output_markdown

def test_shell_backend_timeout(hang_script, tmp_path):
    backend = ShellDocgenBackend(
        script=Path(sys.executable),
        args=[str(hang_script)],
        timeout_seconds=1 # Short timeout
    )

    result = backend.generate_for_file(
        repo_root=tmp_path,
        relative_path=Path("foo.py"),
        file_sha256="deadbeef",
        source_contents="print('hello')",
        existing_doc_contents=None,
        graph_context=None
    )

    assert result.status == "skipped"
    assert "timed out" in result.reason

def test_shell_backend_garbage_output(garbage_script, tmp_path):
    backend = ShellDocgenBackend(
        script=Path(sys.executable),
        args=[str(garbage_script)],
        timeout_seconds=5
    )

    result = backend.generate_for_file(
        repo_root=tmp_path,
        relative_path=Path("foo.py"),
        file_sha256="deadbeef",
        source_contents="print('hello')",
        existing_doc_contents=None,
        graph_context=None
    )

    assert result.status == "skipped"
    assert "missing SHA256 header" in result.reason

def test_shell_backend_mismatched_sha(echo_script, tmp_path):
    # Create a script that lies about SHA
    script_path = tmp_path / "liar_script.py"
    script_content = """
import sys
print("SHA256: wrongsha")
"""
    script_path.write_text(script_content)

    backend = ShellDocgenBackend(
        script=Path(sys.executable),
        args=[str(script_path)],
        timeout_seconds=5
    )

    result = backend.generate_for_file(
        repo_root=tmp_path,
        relative_path=Path("foo.py"),
        file_sha256="deadbeef",
        source_contents="print('hello')",
        existing_doc_contents=None,
        graph_context=None
    )

    assert result.status == "skipped"
    assert "mismatched SHA256" in result.reason

def test_unicode_bomb(echo_script, tmp_path):
    # Test with emojis and non-ascii
    unicode_content = "Hello 🌍 🚀"
    backend = ShellDocgenBackend(
        script=Path(sys.executable),
        args=[str(echo_script)],
        timeout_seconds=5
    )

    result = backend.generate_for_file(
        repo_root=tmp_path,
        relative_path=Path("foo.py"),
        file_sha256="deadbeef",
        source_contents=unicode_content,
        existing_doc_contents=None,
        graph_context=None
    )
    
    assert result.status == "generated"

