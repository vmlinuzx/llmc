"""
Tool Envelope unit tests.

Tests sniffer, config, store, formatter, and grep handler.
"""

from __future__ import annotations

import os
from pathlib import Path

from llmc.te.config import DEFAULT_AGENT_BUDGETS, get_output_budget
from llmc.te.formatter import (
    FormattedOutput,
    TeMeta,
    compute_hot_zone,
    format_breadcrumb,
    format_meta_header,
)
from llmc.te.sniffer import sniff
from llmc.te.store import clear, get_entry, list_handles, load, store


class TestSniffer:
    """Test content-type sniffer."""

    def test_extension_map_python(self):
        assert sniff("foo.py") == "code/python"

    def test_extension_map_typescript(self):
        assert sniff("component.tsx") == "code/typescript"

    def test_extension_map_json(self):
        assert sniff("config.json") == "json"

    def test_extension_map_yaml(self):
        assert sniff("docker-compose.yml") == "yaml"

    def test_extension_map_markdown(self):
        assert sniff("README.md") == "markdown"

    def test_log_detection_iso_date(self):
        sample = "2024-01-15 10:30:45 INFO Starting...\n2024-01-15 10:30:46 DEBUG init"
        assert sniff("app.txt", sample) == "log"

    def test_log_detection_level_prefix(self):
        sample = "[ERROR] something failed\n[WARN] potential issue\nmore text"
        assert sniff("output.txt", sample) == "log"

    def test_json_detection_object(self):
        sample = '{"key": "value", "num": 123}'
        assert sniff("data.txt", sample) == "json"

    def test_json_detection_array(self):
        sample = '[1, 2, 3, {"nested": true}]'
        assert sniff("data.txt", sample) == "json"

    def test_fallback_to_text(self):
        assert sniff("unknown.xyz") == "text"
        assert sniff("unknown.xyz", "just regular text") == "text"


class TestConfig:
    """Test config loading and agent budgets."""

    def test_default_agent_budgets_exist(self):
        assert "gemini-shell" in DEFAULT_AGENT_BUDGETS
        assert "claude-dc" in DEFAULT_AGENT_BUDGETS
        assert "qwen-local" in DEFAULT_AGENT_BUDGETS
        assert "unknown" in DEFAULT_AGENT_BUDGETS

    def test_get_output_budget_known_agent(self):
        budget = get_output_budget("claude-dc")
        assert budget == 180_000

    def test_get_output_budget_unknown_agent(self):
        budget = get_output_budget("random-agent-xyz")
        assert budget == DEFAULT_AGENT_BUDGETS["unknown"]

    def test_get_output_budget_env_override(self):
        """Budget lookup respects TE_AGENT_ID env."""
        os.environ["TE_AGENT_ID"] = "gemini-shell"
        try:
            budget = get_output_budget(None)
            assert budget == 900_000
        finally:
            del os.environ["TE_AGENT_ID"]


class TestStore:
    """Test in-memory handle store."""

    def setup_method(self):
        clear()

    def test_store_and_load(self):
        data = "test result data"
        handle = store(data, "grep", len(data))
        assert handle.startswith("res_")
        loaded = load(handle)
        assert loaded == data

    def test_load_miss(self):
        assert load("nonexistent_handle") is None

    def test_get_entry_metadata(self):
        data = "test data"
        handle = store(data, "grep", 100)
        entry = get_entry(handle)
        assert entry is not None
        assert entry.cmd == "grep"
        assert entry.total_size == 100
        assert entry.created > 0

    def test_list_handles(self):
        h1 = store("data1", "grep", 10)
        h2 = store("data2", "cat", 20)
        handles = list_handles()
        assert h1 in handles
        assert h2 in handles

    def test_clear(self):
        store("data", "grep", 10)
        count = clear()
        assert count == 1
        assert list_handles() == []


class TestFormatter:
    """Test MPD meta header and breadcrumb formatting."""

    def test_meta_header_basic(self):
        meta = TeMeta(cmd="grep", matches=10, files=3)
        header = format_meta_header(meta)
        assert "# TE_BEGIN_META" in header
        assert "# TE_END_META" in header
        assert '"cmd": "grep"' in header or '"cmd":"grep"' in header
        assert '"matches": 10' in header or '"matches":10' in header

    def test_meta_header_excludes_none(self):
        meta = TeMeta(cmd="grep", matches=5)
        header = format_meta_header(meta)
        # truncated is None, should not appear
        assert "truncated" not in header

    def test_meta_header_truncated(self):
        meta = TeMeta(cmd="grep", matches=100, truncated=True, handle="res_abc123")
        header = format_meta_header(meta)
        assert '"truncated": true' in header or '"truncated":true' in header
        assert '"handle": "res_abc123"' in header or '"handle":"res_abc123"' in header

    def test_breadcrumb_format(self):
        bc = format_breadcrumb("42 more in tools/")
        assert bc == "\n# TE: 42 more in tools/"

    def test_formatted_output_render(self):
        meta = TeMeta(cmd="grep", matches=2)
        output = FormattedOutput(
            header=format_meta_header(meta),
            content="file.py:1: def foo():\nfile.py:5: def bar():",
            breadcrumbs=[format_breadcrumb("more results available")],
        )
        rendered = output.render()
        assert "# TE_BEGIN_META" in rendered
        assert "file.py:1:" in rendered
        assert "# TE: more results available" in rendered

    def test_compute_hot_zone_dominant(self):
        """Hot zone shows when >50% in one area."""
        file_counts = {
            "tools/rag": 70,
            "tests": 20,
            "scripts": 10,
        }
        hot_zone = compute_hot_zone(file_counts, 100)
        assert hot_zone is not None
        assert "tools/rag" in hot_zone
        assert "70%" in hot_zone

    def test_compute_hot_zone_no_dominant(self):
        """No hot zone when evenly distributed."""
        file_counts = {
            "tools": 30,
            "tests": 30,
            "scripts": 30,
        }
        hot_zone = compute_hot_zone(file_counts, 90)
        assert hot_zone is None

    def test_compute_hot_zone_small_result(self):
        """No hot zone for small results."""
        file_counts = {"tools": 3}
        hot_zone = compute_hot_zone(file_counts, 3)
        assert hot_zone is None


class TestGrepHandler:
    """Test grep handler."""

    def test_grep_simple_match(self):
        """Grep finds matches."""
        from llmc.te.handlers.grep import handle_grep

        result = handle_grep("def handle_grep", repo_root=Path("/home/vmlinux/src/llmc"))
        assert "# TE_BEGIN_META" in result.header
        assert '"cmd": "grep"' in result.header or '"cmd":"grep"' in result.header
        assert "handle_grep" in result.content

    def test_grep_no_match(self):
        """Grep handles no matches gracefully."""
        import uuid

        from llmc.te.handlers.grep import handle_grep

        # Generate a UUID pattern that won't match anything
        unique_pattern = f"nomatch_{uuid.uuid4().hex}"
        result = handle_grep(unique_pattern, repo_root=Path("/home/vmlinux/src/llmc"))
        assert '"matches": 0' in result.header or '"matches":0' in result.header

    def test_grep_raw_bypass(self):
        """Raw mode skips enrichment."""
        from llmc.te.handlers.grep import handle_grep

        result = handle_grep("def handle_grep", raw=True, repo_root=Path("/home/vmlinux/src/llmc"))
        # Raw mode has no header
        assert result.header == ""
        # Content is raw rg output
        assert "handle_grep" in result.content

    def test_grep_invalid_pattern(self):
        """Invalid regex returns error in meta."""
        from llmc.te.handlers.grep import handle_grep

        result = handle_grep("[invalid", repo_root=Path("/home/vmlinux/src/llmc"))
        assert '"error":' in result.header or '"error": ' in result.header


class TestDefinitionRanking:
    """Test that definitions rank higher than usages."""

    def test_is_definition_python(self):
        from llmc.te.handlers.grep import _is_definition

        assert _is_definition("def foo():") is True
        assert _is_definition("class MyClass:") is True
        assert _is_definition("    def method(self):") is True
        assert _is_definition("foo()") is False
        assert _is_definition("x = foo()") is False

    def test_is_definition_javascript(self):
        from llmc.te.handlers.grep import _is_definition

        assert _is_definition("function foo() {") is True
        assert _is_definition("const foo = () => {") is True
        assert _is_definition("export default function bar() {") is True
        assert _is_definition("foo.bar()") is False

    def test_is_test_file(self):
        from llmc.te.handlers.grep import _is_test_file

        assert _is_test_file("tests/test_foo.py") is True
        assert _is_test_file("foo_test.py") is True
        assert _is_test_file("foo.test.js") is True
        assert _is_test_file("__tests__/component.tsx") is True
        assert _is_test_file("src/foo.py") is False
        assert _is_test_file("tools/rag/database.py") is False
