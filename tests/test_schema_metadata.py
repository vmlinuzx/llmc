"""
Schema metadata tests for tools.rag.schema

Covers:
- Core Entity/Relation/SchemaGraph fields
- Round-trip serialization
- Backwards compatibility with older payloads
- Language detection helper
- Phase 2 Entity location fields (file_path, start_line, end_line)
"""

import sys
from pathlib import Path


# Ensure the project root is on sys.path for imports
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_schema_core_fields():
    """Schema metadata should expose core fields on Entity."""
    from tools.rag.schema import Entity

    entity = Entity(
        id="test:function_one",
        kind="function",
        path="test.py:5-10",
        metadata={"docstring": "Test function", "visibility": "public"},
    )

    assert entity.id == "test:function_one"
    assert entity.kind == "function"
    assert entity.path == "test.py:5-10"
    assert "docstring" in entity.metadata
    assert "visibility" in entity.metadata


def test_schema_round_trip():
    """Entities and relations should round-trip through SchemaGraph.to_dict/from_dict."""
    from tools.rag.schema import Entity, Relation, SchemaGraph

    func1 = Entity(
        id="module:func_a",
        kind="function",
        path="module.py:10-20",
        metadata={"returns": "int"},
    )

    func2 = Entity(
        id="module:func_b",
        kind="function",
        path="module.py:25-35",
        metadata={"returns": "str"},
    )

    relation = Relation(
        src="module:func_a",
        edge="calls",
        dst="module:func_b",
    )

    graph = SchemaGraph()
    graph.entities = [func1, func2]
    graph.relations = [relation]

    graph_dict = graph.to_dict()
    graph2 = SchemaGraph.from_dict(graph_dict)

    assert len(graph2.entities) == 2
    assert len(graph2.relations) == 1
    assert graph2.entities[0].id == "module:func_a"
    assert graph2.entities[1].id == "module:func_b"
    assert graph2.relations[0].src == "module:func_a"
    assert graph2.relations[0].edge == "calls"
    assert graph2.relations[0].dst == "module:func_b"


def test_schema_backwards_compatibility():
    """Older schema payloads without location fields should still load."""
    from tools.rag.schema import SchemaGraph

    old_schema = {
        "version": 1,
        "indexed_at": "2024-01-01T00:00:00",
        "repo": "/tmp/test",
        "entities": [
            {
                "id": "old:entity",
                "kind": "function",
                "path": "old.py:1-10",
                "metadata": {},
            }
        ],
        "relations": [],
    }

    graph = SchemaGraph.from_dict(old_schema)

    assert graph.version == 1
    assert len(graph.entities) == 1
    assert graph.entities[0].id == "old:entity"
    assert isinstance(graph.entities[0].metadata, dict)


def test_language_detection():
    """language_for_path should map known extensions and ignore unknown ones."""
    from tools.rag.schema import language_for_path

    cases = [
        (Path("test.py"), "python"),
        (Path("test.ts"), "typescript"),
        (Path("test.js"), "javascript"),
        (Path("test.java"), "java"),
        (Path("test.go"), "go"),
        (Path("test.txt"), None),
        (Path("test.unknown"), None),
    ]

    for path, expected in cases:
        assert language_for_path(path) == expected


def test_entity_location_fields_round_trip():
    """Entity location fields should survive SchemaGraph round-trip."""
    from tools.rag.schema import Entity, SchemaGraph

    entity = Entity(
        id="test:function_with_location",
        kind="function",
        path="src/module.py:10-20",
        metadata={"docstring": "Has location"},
        file_path="src/module.py",
        start_line=10,
        end_line=20,
    )

    graph = SchemaGraph(
        version=1,
        indexed_at="2025-01-01T00:00:00Z",
        repo="/tmp/repo",
        entities=[entity],
        relations=[],
    )

    payload = graph.to_dict()
    entity_payload = payload["entities"][0]

    assert entity_payload["file_path"] == "src/module.py"
    assert entity_payload["start_line"] == 10
    assert entity_payload["end_line"] == 20

    graph_round_trip = SchemaGraph.from_dict(payload)
    entity_rt = graph_round_trip.entities[0]

    assert entity_rt.file_path == "src/module.py"
    assert entity_rt.start_line == 10
    assert entity_rt.end_line == 20
    assert entity_rt.start_line <= entity_rt.end_line

