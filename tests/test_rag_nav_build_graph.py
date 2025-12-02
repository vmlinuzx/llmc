import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rag_nav.metadata import load_status  # type: ignore  # noqa: E402
from tools.rag_nav.tool_handlers import (  # type: ignore  # noqa: E402
    _graph_path,  # type: ignore[attr-defined]
    build_graph_for_repo,
)


def test_build_graph_creates_graph_and_status(tmp_path: Path) -> None:
    # Arrange: create a tiny fake repo with a couple of .py files.
    repo_root = tmp_path
    (repo_root / "module_a.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    pkg_dir = repo_root / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    # Create two classes with an inheritance edge to exercise relations.
    (pkg_dir / "module_b.py").write_text(
        "class Base:\n    pass\n\nclass Child(Base):\n    pass\n",
        encoding="utf-8",
    )

    # Act: build graph.
    status = build_graph_for_repo(repo_root)

    # Assert: status persisted and marked fresh.
    loaded = load_status(repo_root)
    assert loaded is not None
    assert loaded.index_state == "fresh"
    assert loaded.schema_version == "2"

    # Assert: graph file exists and lists the .py files we created.
    graph_path = _graph_path(repo_root)
    assert graph_path.is_file()

    data = json.loads(graph_path.read_text(encoding="utf-8"))
    assert data.get("repo") == str(repo_root.resolve())
    assert data.get("schema_version") == "2"
    files = data.get("files") or []
    # Expect relative paths.
    assert "module_a.py" in files
    assert "pkg/module_b.py" in files

    # Assert: schema_graph is present with entities and at least one relation.
    schema_graph = data.get("schema_graph") or {}
    entities = schema_graph.get("entities") or []
    relations = schema_graph.get("relations") or []
    assert entities
    # Basic sanity: we indexed both modules.
    assert any("module_a.py" in e.get("path", "") for e in entities)
    assert any("pkg/module_b.py" in e.get("path", "") for e in entities)
    # Inheritance edge from Child(Base) should produce at least one relation.
    assert any(r.get("edge") == "extends" for r in relations)
