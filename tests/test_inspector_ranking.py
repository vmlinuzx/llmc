from unittest.mock import patch

import pytest

from llmc.rag.inspector import inspect_entity
from llmc.rag.schema import Entity, Relation, SchemaGraph


@pytest.fixture
def mock_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".llmc").mkdir()
    (repo / ".llmc" / "rag_graph.json").touch()
    return repo


@pytest.fixture
def mock_graph():
    graph = SchemaGraph()
    # Create some entities
    # 1. Public Class (Important)
    graph.entities.append(
        Entity(
            id="type:module.PublicClass",
            kind="class",
            path="module.py:10-50",
            file_path="module.py",
            start_line=10,
            end_line=50,
        )
    )
    # 2. Private Helper Function (Less Important)
    graph.entities.append(
        Entity(
            id="sym:module._helper",
            kind="function",
            path="module.py:60-70",
            file_path="module.py",
            start_line=60,
            end_line=70,
        )
    )
    # 3. Public Function (Important)
    graph.entities.append(
        Entity(
            id="sym:module.public_func",
            kind="function",
            path="module.py:80-100",
            file_path="module.py",
            start_line=80,
            end_line=100,
        )
    )
    # 4. Small Variable (Least Important)
    graph.entities.append(
        Entity(
            id="sym:module.CONST",
            kind="variable",
            path="module.py:5-5",
            file_path="module.py",
            start_line=5,
            end_line=5,
        )
    )

    # Add some relations to boost importance
    # PublicClass is used by something
    graph.relations.append(
        Relation(src="sym:other.func", edge="uses", dst="type:module.PublicClass")
    )

    return graph


def test_inspect_entity_ranking(mock_repo, mock_graph):
    # Mock file content
    (mock_repo / "module.py").write_text("\n" * 100)

    with patch("llmc.rag.inspector.SchemaGraph.load", return_value=mock_graph):
        # Inspect the file
        result = inspect_entity(mock_repo, path="module.py")

        # Check defined_symbols order
        # Current behavior: sorted by line number
        # Expected behavior (after fix): Ranked by importance

        symbols = result.defined_symbols
        names = [s.name for s in symbols]

        print(f"Symbols: {names}")

        # If we implement ranking, we expect PublicClass and public_func to be at the top
        # Currently it will be CONST, PublicClass, _helper, public_func (by line number)

        # We want to assert that the ranking logic works once implemented.
        # For now, let's just see what we get.


if __name__ == "__main__":
    # Manually run if executed as script
    pass
