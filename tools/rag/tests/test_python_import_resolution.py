
import pytest

from tools.rag.schema import (
    build_graph_for_repo,
)


# Helper function to create temporary files and build graph
@pytest.fixture
def repo_with_files(tmp_path):
    def _create_repo(files_dict):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        for file_name, content in files_dict.items():
            (repo_root / file_name).write_text(content, encoding="utf-8")
        return repo_root
    return _create_repo


def get_call_relations(graph) -> list[tuple[str, str]]:
    """Helper to extract (src, dst) of 'calls' relations."""
    return [(rel.src, rel.dst) for rel in graph.relations if rel.edge == "calls"]


# --- Test Cases from SDD ---

def test_imported_function_call_targets_definer(repo_with_files):
    """
    Verifies that a direct call to an imported function correctly
    targets the definer module's symbol.
    """
    repo_root = repo_with_files({
        "definer.py": """
def hello():
    pass
""",
        "importer.py": """
from definer import hello

def caller():
    hello()
""",
    })

    graph = build_graph_for_repo(repo_root, require_enrichment=False)
    calls = get_call_relations(graph)

    # Expected: importer.caller calls definer.hello
    assert ("sym:importer.caller", "sym:definer.hello") in calls
    # Guardrail: no phantom local stub
    assert ("sym:importer.caller", "sym:importer.hello") not in calls


def test_module_alias_call_resolves_via_import_map(repo_with_files):
    """
    Verifies that a call through a module alias correctly targets
    the definer module's symbol.
    """
    repo_root = repo_with_files({
        "definer.py": """
def hello():
    pass
""",
        "importer.py": """
import definer as d

def caller():
    d.hello()
""",
    })

    graph = build_graph_for_repo(repo_root, require_enrichment=False)
    calls = get_call_relations(graph)

    # Expected: importer.caller calls definer.hello
    assert ("sym:importer.caller", "sym:definer.hello") in calls
    # Guardrail: no phantom local stub for 'd.hello'
    assert ("sym:importer.caller", "sym:importer.d.hello") not in calls


def test_imported_function_alias_resolves(repo_with_files):
    """
    Verifies that a call to an aliased imported function correctly
    targets the definer module's symbol.
    """
    repo_root = repo_with_files({
        "definer.py": """
def hello():
    pass
""",
        "importer.py": """
from definer import hello as hi

def caller():
    hi()
""",
    })

    graph = build_graph_for_repo(repo_root, require_enrichment=False)
    calls = get_call_relations(graph)

    # Expected: importer.caller calls definer.hello
    assert ("sym:importer.caller", "sym:definer.hello") in calls
    # Guardrail: no phantom local stub for 'hi'
    assert ("sym:importer.caller", "sym:importer.hi") not in calls


# --- Additional Test Cases for Robustness ---

def test_local_function_call_is_unaffected(repo_with_files):
    """
    Ensures that calls to local functions are still correctly resolved
    to the current module.
    """
    repo_root = repo_with_files({
        "local_module.py": """
def my_local_func():
    pass

def caller():
    my_local_func()
""",
    })

    graph = build_graph_for_repo(repo_root, require_enrichment=False)
    calls = get_call_relations(graph)

    assert ("sym:local_module.caller", "sym:local_module.my_local_func") in calls


def test_multiple_imports_from_same_module(repo_with_files):
    """
    Tests multiple imports from the same module, ensuring all resolve correctly.
    """
    repo_root = repo_with_files({
        "lib.py": """
def func_a(): pass
def func_b(): pass
""",
        "app.py": """
from lib import func_a, func_b

def main():
    func_a()
    func_b()
""",
    })

    graph = build_graph_for_repo(repo_root, require_enrichment=False)
    calls = get_call_relations(graph)

    assert ("sym:app.main", "sym:lib.func_a") in calls
    assert ("sym:app.main", "sym:lib.func_b") in calls


def test_import_module_and_call_directly(repo_with_files):
    """
    Tests 'import module' and then 'module.func()' call.
    """
    repo_root = repo_with_files({
        "utils.py": """
def helper_func(): pass
""",
        "main.py": """
import utils

def execute():
    utils.helper_func()
""",
    })

    graph = build_graph_for_repo(repo_root, require_enrichment=False)
    calls = get_call_relations(graph)

    assert ("sym:main.execute", "sym:utils.helper_func") in calls


def test_non_existent_import_still_local_fallback(repo_with_files):
    """
    Ensures that if an import target does not exist (e.g., misspelled),
    it still falls back to a local symbol, as we don't have static analysis
    to validate imports.
    """
    repo_root = repo_with_files({
        "importer.py": """
from non_existent_module import non_existent_func

def caller():
    non_existent_func()
""",
    })

    graph = build_graph_for_repo(repo_root, require_enrichment=False)
    calls = get_call_relations(graph)

    # We expect it to construct a symbol ID based on the imported module,
    # as the extractor processes the import statement directly.
    assert ("sym:importer.caller", "sym:non_existent_module.non_existent_func") in calls

