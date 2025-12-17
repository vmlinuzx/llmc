"""
Tests for docgen configuration loading.
"""

from pathlib import Path

import pytest

from llmc.docgen.config import (
    DocgenConfigError,
    get_output_dir,
    get_require_rag_fresh,
    load_docgen_backend,
)


def test_load_docgen_backend_no_docs_section():
    """Test loading with no [docs] section returns None."""
    toml_data = {}
    result = load_docgen_backend(Path("/tmp"), toml_data)
    assert result is None


def test_load_docgen_backend_no_docgen_section():
    """Test loading with no [docs.docgen] section returns None."""
    toml_data = {"docs": {}}
    result = load_docgen_backend(Path("/tmp"), toml_data)
    assert result is None


def test_load_docgen_backend_disabled():
    """Test loading with enabled=false returns None."""
    toml_data = {"docs": {"docgen": {"enabled": False, "backend": "shell"}}}
    result = load_docgen_backend(Path("/tmp"), toml_data)
    assert result is None


def test_load_docgen_backend_missing_backend_field():
    """Test loading with missing backend field raises error."""
    toml_data = {"docs": {"docgen": {"enabled": True}}}
    with pytest.raises(DocgenConfigError, match="Missing 'backend' field"):
        load_docgen_backend(Path("/tmp"), toml_data)


def test_load_docgen_backend_invalid_backend_type():
    """Test loading with invalid backend type raises error."""
    toml_data = {"docs": {"docgen": {"enabled": True, "backend": "invalid_backend"}}}
    with pytest.raises(
        DocgenConfigError, match="Invalid backend type 'invalid_backend'"
    ):
        load_docgen_backend(Path("/tmp"), toml_data)


def test_load_docgen_backend_shell_missing_config():
    """Test loading shell backend without script config raises error."""
    toml_data = {"docs": {"docgen": {"enabled": True, "backend": "shell"}}}
    with pytest.raises(ValueError, match="Missing 'shell.script'"):
        load_docgen_backend(Path("/tmp"), toml_data)


def test_load_docgen_backend_llm_not_implemented():
    """Test loading LLM backend raises error (not yet implemented)."""
    toml_data = {"docs": {"docgen": {"enabled": True, "backend": "llm"}}}
    with pytest.raises(DocgenConfigError, match="LLM backend not yet implemented"):
        load_docgen_backend(Path("/tmp"), toml_data)


def test_load_docgen_backend_http_not_implemented():
    """Test loading HTTP backend raises error (not yet implemented)."""
    toml_data = {"docs": {"docgen": {"enabled": True, "backend": "http"}}}
    with pytest.raises(DocgenConfigError, match="HTTP backend not yet implemented"):
        load_docgen_backend(Path("/tmp"), toml_data)


def test_load_docgen_backend_mcp_not_implemented():
    """Test loading MCP backend raises error (not yet implemented)."""
    toml_data = {"docs": {"docgen": {"enabled": True, "backend": "mcp"}}}
    with pytest.raises(DocgenConfigError, match="MCP backend not yet implemented"):
        load_docgen_backend(Path("/tmp"), toml_data)


def test_get_output_dir_default():
    """Test get_output_dir returns default when not configured."""
    assert get_output_dir({}) == "DOCS/REPODOCS"
    assert get_output_dir({"docs": {}}) == "DOCS/REPODOCS"
    assert get_output_dir({"docs": {"docgen": {}}}) == "DOCS/REPODOCS"


def test_get_output_dir_custom():
    """Test get_output_dir returns custom value when configured."""
    toml_data = {"docs": {"docgen": {"output_dir": "custom/docs/path"}}}
    assert get_output_dir(toml_data) == "custom/docs/path"


def test_get_require_rag_fresh_default():
    """Test get_require_rag_fresh returns default (True) when not configured."""
    assert get_require_rag_fresh({}) is True
    assert get_require_rag_fresh({"docs": {}}) is True
    assert get_require_rag_fresh({"docs": {"docgen": {}}}) is True


def test_get_require_rag_fresh_custom():
    """Test get_require_rag_fresh returns custom value when configured."""
    toml_data = {"docs": {"docgen": {"require_rag_fresh": False}}}
    assert get_require_rag_fresh(toml_data) is False

    toml_data["docs"]["docgen"]["require_rag_fresh"] = True
    assert get_require_rag_fresh(toml_data) is True
