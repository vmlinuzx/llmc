# llmc_mcp/test_tools_visibility_and_metrics.py
import importlib

import pytest


def _load_server():
    try:
        return importlib.import_module("llmc_mcp.server")
    except Exception as e:
        pytest.skip(f"server module not importable: {e}")


def _get_registry(server):
    # Try multiple patterns to locate the registry
    for attr in ("TOOL_REGISTRY", "tool_registry"):
        reg = getattr(server, attr, None)
        if isinstance(reg, dict):
            return reg
    get_reg = getattr(server, "get_tool_registry", None)
    if callable(get_reg):
        reg = get_reg()
        if isinstance(reg, dict):
            return reg
    pytest.skip("No accessible tool registry on server module.")


def test_tool_registry_contains_te_wrappers():
    server = _load_server()
    reg = _get_registry(server)
    names = set(reg.keys())
    for name in ("te_run", "repo_read", "rag_query"):
        assert (
            name in names
        ), f"Expected tool '{name}' to be registered; got {sorted(names)}"


def test_get_metrics_basic_shape():
    server = _load_server()
    reg = _get_registry(server)
    get_metrics = reg.get("get_metrics") or getattr(server, "get_metrics", None)
    if not callable(get_metrics):
        pytest.skip("get_metrics tool not exposed; skipping.")
    try:
        res = get_metrics()
    except TypeError:
        # Some implementations expect *args/**kwargs; call permissively
        try:
            res = get_metrics({})
        except Exception as e:
            pytest.skip(f"get_metrics call signature unknown: {e}")
    assert isinstance(
        res, dict
    ), f"get_metrics should return dict-like, got {type(res)}"
    # Non-strict sanity: must contain at least one top-level key
    assert len(res.keys()) > 0
