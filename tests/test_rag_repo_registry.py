from pathlib import Path

from llmc.rag_repo.models import RegistryEntry, ToolConfig
from llmc.rag_repo.registry import RegistryAdapter


def test_registry_round_trip(tmp_path: Path) -> None:
    cfg = ToolConfig(registry_path=tmp_path / "repos.yml")
    adapter = RegistryAdapter(cfg)

    entry = RegistryEntry(
        repo_id="repo-1",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
        display_name="Test Repo",
        rag_profile="default",
    )
    adapter.register(entry)

    entries = adapter.load_all()
    assert "repo-1" in entries

    loaded = entries["repo-1"]
    assert loaded.repo_id == "repo-1"
    assert loaded.display_name == "Test Repo"

    ok = adapter.unregister_by_id("repo-1")
    assert ok is True
    assert "repo-1" not in adapter.load_all()
