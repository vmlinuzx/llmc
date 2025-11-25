from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rag_nav.tool_handlers import (  # type: ignore  # noqa: E402
    build_graph_for_repo,
    tool_rag_lineage,
    tool_rag_search,
    tool_rag_where_used,
)


def _setup_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path
    (repo_root / "module_a.py").write_text(
        """    def target_symbol():
    return 1
""",
        encoding="utf-8",
    )
    (repo_root / "module_b.py").write_text(
        """    from module_a import target_symbol

def use_it():
    return target_symbol()
""",
        encoding="utf-8",
    )
    build_graph_for_repo(repo_root)
    return repo_root


def test_tool_rag_search_finds_symbol(tmp_path: Path) -> None:
    repo_root = _setup_repo(tmp_path)

    result = tool_rag_search(query="target_symbol", repo_root=repo_root, limit=10)

    assert result.items
    first = result.items[0]
    assert "target_symbol" in first.snippet.text
    assert first.snippet.location.path.endswith(".py")
    assert result.source in ("RAG_GRAPH", "LOCAL_FALLBACK")
    assert result.freshness_state in ("FRESH", "STALE", "UNKNOWN")


def test_tool_rag_where_used_finds_call_sites(tmp_path: Path) -> None:
    repo_root = _setup_repo(tmp_path)

    result = tool_rag_where_used(symbol="target_symbol", repo_root=repo_root, limit=10)

    assert result.items
    paths = {item.file for item in result.items}
    assert "module_b.py" in paths or any("module_b.py" in p for p in paths)
    assert result.source in ("RAG_GRAPH", "LOCAL_FALLBACK")
    assert result.freshness_state in ("FRESH", "STALE", "UNKNOWN")


def test_tool_rag_lineage_returns_items(tmp_path: Path) -> None:
    repo_root = _setup_repo(tmp_path)

    result = tool_rag_lineage(
        symbol="target_symbol",
        direction="downstream",
        repo_root=repo_root,
        max_results=10,
    )

    assert result.items
    assert result.direction in ("upstream", "downstream")
    assert result.source in ("RAG_GRAPH", "LOCAL_FALLBACK")
    assert result.freshness_state in ("FRESH", "STALE", "UNKNOWN")
