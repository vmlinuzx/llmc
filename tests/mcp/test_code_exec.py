"""Tests for code execution mode - the Anthropic 'Code Mode' pattern."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


# Mock Tool class to avoid mcp dependency in tests
@dataclass
class MockTool:
    name: str
    description: str
    inputSchema: dict[str, Any]


# Alias for compatibility
Tool = MockTool

from llmc_mcp.tools.code_exec import execute_code, generate_stubs


def make_mock_tool_caller(results: dict):
    """Create a mock tool caller that returns predefined results."""

    def caller(name: str, args: dict) -> dict:
        return results.get(name, {"error": f"Unknown tool: {name}"})

    return caller


class TestExecuteCode:
    """Test execute_code function."""

    def test_simple_print(self):
        """Basic code execution with stdout capture."""
        result = execute_code(
            code='print("hello world")',
            tool_caller=lambda n, a: {},
        )
        assert result.success
        assert "hello world" in result.stdout

    def test_call_tool_injection(self):
        """Verify _call_tool is available in executed code namespace."""
        mock_caller = make_mock_tool_caller(
            {"test_tool": {"data": "mock_result", "meta": {}}}
        )

        result = execute_code(
            code="""
result = _call_tool("test_tool", {"arg": "value"})
print(f"Got: {result}")
""",
            tool_caller=mock_caller,
        )
        assert result.success
        assert "mock_result" in result.stdout

    def test_import_stub_calls_injected_tool(self, tmp_path):
        """
        Critical test: Verify that imported stubs use builtins._call_tool.

        This was the bug - stubs imported _call_tool from the module which
        raised NotImplementedError, instead of using the injected version.
        """
        # Generate a test stub
        test_tool = Tool(
            name="my_test_tool",
            description="A test tool",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Test query"}
                },
                "required": ["query"],
            },
        )

        stubs_dir = tmp_path / "stubs"
        generate_stubs([test_tool], Path("stubs"), tmp_path)

        # Mock caller that records what was called
        calls = []

        def tracking_caller(name: str, args: dict) -> dict:
            calls.append((name, args))
            return {"data": "success", "meta": {}}

        # Execute code that imports and uses the stub
        result = execute_code(
            code="""
from stubs import my_test_tool
result = my_test_tool(query="test query")
print(f"Result: {result}")
""",
            tool_caller=tracking_caller,
            stubs_dir=stubs_dir,
        )

        assert (
            result.success
        ), f"Execution failed: {result.error}\nstderr: {result.stderr}"
        assert len(calls) == 1, f"Expected 1 call, got {len(calls)}"
        assert calls[0][0] == "my_test_tool"
        assert "query" in calls[0][1]
        assert "success" in result.stdout

    def test_builtins_cleanup(self):
        """Verify builtins._call_tool is cleaned up after execution."""
        import builtins

        # Ensure clean state
        if hasattr(builtins, "_call_tool"):
            delattr(builtins, "_call_tool")

        result = execute_code(
            code='print("test")',
            tool_caller=lambda n, a: {},
        )

        assert result.success
        # _call_tool should be cleaned up
        assert not hasattr(
            builtins, "_call_tool"
        ), "builtins._call_tool should be cleaned up"

    def test_timeout_capture(self):
        """Test that stderr is captured on error."""
        result = execute_code(
            code='raise ValueError("test error")',
            tool_caller=lambda n, a: {},
        )

        assert not result.success
        assert "ValueError" in result.error

    def test_max_output_truncation(self):
        """Test output truncation at max_output_bytes."""
        result = execute_code(
            code='print("x" * 10000)',
            tool_caller=lambda n, a: {},
            max_output_bytes=100,
        )

        assert result.success
        assert len(result.stdout) <= 100


class TestGenerateStubs:
    """Test stub generation."""

    def test_generates_stub_files(self, tmp_path):
        """Test that stub files are generated correctly."""
        tool = Tool(
            name="test_tool",
            description="Test description",
            inputSchema={
                "type": "object",
                "properties": {
                    "required_arg": {"type": "string", "description": "Required"},
                    "optional_arg": {
                        "type": "integer",
                        "description": "Optional",
                        "default": 10,
                    },
                },
                "required": ["required_arg"],
            },
        )

        generated = generate_stubs([tool], Path("stubs"), tmp_path)

        assert "test_tool" in generated
        stub_path = Path(generated["test_tool"])
        assert stub_path.exists()

        content = stub_path.read_text()
        assert "def test_tool(" in content
        assert "required_arg: str" in content
        assert "optional_arg: int = 10" in content
        assert "Test description" in content
        # Critical: Should NOT import _call_tool
        assert "from llmc_mcp.tools.code_exec import _call_tool" not in content

    def test_generates_init_and_readme(self, tmp_path):
        """Test that __init__.py and README.md are generated."""
        tool = Tool(
            name="dummy",
            description="Dummy",
            inputSchema={"type": "object", "properties": {}, "required": []},
        )

        generated = generate_stubs([tool], Path("stubs"), tmp_path)

        assert "__init__" in generated
        assert "README" in generated

        init_content = Path(generated["__init__"]).read_text()
        assert "from .dummy import dummy" in init_content
