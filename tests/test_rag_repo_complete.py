"""Comprehensive test suite for LLMC RAG Repo Registration Tool."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from tools.rag_repo.config import load_tool_config
from tools.rag_repo.inspect_repo import inspect_repo
from tools.rag_repo.models import RegistryEntry, RepoInspection, ToolConfig
from tools.rag_repo.notifier import notify_refresh, notify_refresh_all
from tools.rag_repo.registry import RegistryAdapter
from tools.rag_repo.utils import canonical_repo_path, generate_repo_id
from tools.rag_repo.workspace import init_workspace, plan_workspace, validate_workspace

# ==============================================================================
# 7. Repo Registration Tool Tests
# ==============================================================================


def test_tool_config_default(tmp_path: Path) -> None:
    """Test loading tool config with defaults."""
    # No config file exists, should return defaults
    config_file = tmp_path / "nonexistent.yml"

    with patch("os.environ.get") as mock_env:
        mock_env.return_value = str(config_file)
        config = load_tool_config()

    assert config.registry_path.name == "repos.yml"
    assert config.default_workspace_folder_name == ".llmc/rag"
    assert config.default_rag_profile == "default"


def test_tool_config_custom_path(tmp_path: Path) -> None:
    """Test loading tool config from custom path."""
    config_file = tmp_path / "custom-config.yml"
    config_file.write_text(
        yaml.dump(
            {
                "registry_path": "~/custom/repos.yml",
                "default_workspace_folder_name": ".custom/rag",
                "default_rag_profile": "custom",
                "daemon_control_path": "~/custom/control",
            }
        )
    )

    with patch("os.environ.get") as mock_env:
        mock_env.return_value = str(config_file)
        config = load_tool_config()

    assert "custom/repos.yml" in str(config.registry_path)
    assert config.default_workspace_folder_name == ".custom/rag"
    assert config.default_rag_profile == "custom"


def test_registry_add_new_repo(tmp_path: Path) -> None:
    """Test adding a new repo to registry."""
    registry_file = tmp_path / "repos.yml"
    tool_config = ToolConfig(registry_path=registry_file)
    adapter = RegistryAdapter(tool_config)

    # Initially empty
    assert adapter.load_all() == {}

    # Add a repo
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    entry = RegistryEntry(
        repo_id="repo-test-123",
        repo_path=repo_path,
        rag_workspace_path=repo_path / ".llmc/rag",
        display_name="Test Repo",
        rag_profile="default",
    )
    adapter.register(entry)

    # Verify it was added
    entries = adapter.load_all()
    assert "repo-test-123" in entries
    assert entries["repo-test-123"].display_name == "Test Repo"
    assert entries["repo-test-123"].repo_path == repo_path


def test_registry_idempotent_add(tmp_path: Path) -> None:
    """Test that adding existing workspace is idempotent."""
    registry_file = tmp_path / "repos.yml"
    tool_config = ToolConfig(registry_path=registry_file)
    adapter = RegistryAdapter(tool_config)

    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    workspace_path = repo_path / ".llmc/rag"
    workspace_path.mkdir(parents=True)

    # Add configs first (simulating existing workspace)
    config_dir = workspace_path / "config"
    config_dir.mkdir(parents=True)
    rag_config = config_dir / "rag.yml"
    rag_config.write_text(yaml.dump({"repo_id": "repo-existing", "display_name": "Existing"}))
    version_config = config_dir / "version.yml"
    version_config.write_text(yaml.dump({"config_version": "v1"}))

    # Add to registry
    entry = RegistryEntry(
        repo_id="repo-existing",
        repo_path=repo_path,
        rag_workspace_path=workspace_path,
        display_name="Existing",
        rag_profile="default",
    )
    adapter.register(entry)

    # Should not have overwritten the existing config
    assert rag_config.exists()
    assert version_config.exists()


def test_registry_list_repos(tmp_path: Path) -> None:
    """Test listing all registered repos."""
    registry_file = tmp_path / "repos.yml"
    tool_config = ToolConfig(registry_path=registry_file)
    adapter = RegistryAdapter(tool_config)

    # Add multiple repos
    for i in range(3):
        repo_path = tmp_path / f"repo{i}"
        repo_path.mkdir()
        entry = RegistryEntry(
            repo_id=f"repo-{i}",
            repo_path=repo_path,
            rag_workspace_path=repo_path / ".llmc/rag",
            display_name=f"Repo {i}",
            rag_profile="default",
        )
        adapter.register(entry)

    # List all
    entries = adapter.list_entries()
    assert len(entries) == 3

    # Check they're sorted by repo_id
    repo_ids = [e.repo_id for e in entries]
    assert repo_ids == sorted(repo_ids)


def test_registry_find_by_path(tmp_path: Path) -> None:
    """Test finding repo by path."""
    registry_file = tmp_path / "repos.yml"
    tool_config = ToolConfig(registry_path=registry_file)
    adapter = RegistryAdapter(tool_config)

    repo_path = tmp_path / "my_repo"
    repo_path.mkdir()

    entry = RegistryEntry(
        repo_id="repo-mine",
        repo_path=repo_path,
        rag_workspace_path=repo_path / ".llmc/rag",
        display_name="My Repo",
        rag_profile="default",
    )
    adapter.register(entry)

    # Find by exact path
    found = adapter.find_by_path(repo_path)
    assert found is not None
    assert found.repo_id == "repo-mine"

    # Not found if different path
    other_path = tmp_path / "other_repo"
    other_path.mkdir()
    assert adapter.find_by_path(other_path) is None


def test_registry_find_by_id(tmp_path: Path) -> None:
    """Test finding repo by ID."""
    registry_file = tmp_path / "repos.yml"
    tool_config = ToolConfig(registry_path=registry_file)
    adapter = RegistryAdapter(tool_config)

    repo_path = tmp_path / "my_repo"
    repo_path.mkdir()

    entry = RegistryEntry(
        repo_id="repo-abc123",
        repo_path=repo_path,
        rag_workspace_path=repo_path / ".llmc/rag",
        display_name="My Repo",
        rag_profile="default",
    )
    adapter.register(entry)

    # Find by ID
    found = adapter.find_by_id("repo-abc123")
    assert found is not None
    assert found.display_name == "My Repo"

    # Not found if wrong ID
    assert adapter.find_by_id("repo-nonexistent") is None


def test_registry_remove_by_path(tmp_path: Path) -> None:
    """Test removing repo by path."""
    registry_file = tmp_path / "repos.yml"
    tool_config = ToolConfig(registry_path=registry_file)
    adapter = RegistryAdapter(tool_config)

    repo_path = tmp_path / "repo_to_remove"
    repo_path.mkdir()

    entry = RegistryEntry(
        repo_id="repo-remove",
        repo_path=repo_path,
        rag_workspace_path=repo_path / ".llmc/rag",
        display_name="To Remove",
        rag_profile="default",
    )
    adapter.register(entry)

    # Verify it's there
    assert adapter.find_by_path(repo_path) is not None

    # Remove
    removed = adapter.unregister_by_id("repo-remove")
    assert removed is True

    # Verify it's gone
    assert adapter.find_by_path(repo_path) is None
    assert adapter.find_by_id("repo-remove") is None


def test_registry_remove_by_repo_id(tmp_path: Path) -> None:
    """Test removing repo by repo_id."""
    registry_file = tmp_path / "repos.yml"
    tool_config = ToolConfig(registry_path=registry_file)
    adapter = RegistryAdapter(tool_config)

    repo_path = tmp_path / "repo_by_id"
    repo_path.mkdir()

    entry = RegistryEntry(
        repo_id="repo-by-id",
        repo_path=repo_path,
        rag_workspace_path=repo_path / ".llmc/rag",
        display_name="By ID",
        rag_profile="default",
    )
    adapter.register(entry)

    # Remove by ID
    removed = adapter.unregister_by_id("repo-by-id")
    assert removed is True

    assert adapter.find_by_id("repo-by-id") is None


def test_registry_remove_nonexistent(tmp_path: Path) -> None:
    """Test removing a non-existent repo."""
    registry_file = tmp_path / "repos.yml"
    tool_config = ToolConfig(registry_path=registry_file)
    adapter = RegistryAdapter(tool_config)

    # Try to remove non-existent repo
    removed = adapter.unregister_by_id("repo-nonexistent")
    assert removed is False


def test_inspect_repo_new(tmp_path: Path) -> None:
    """Test inspecting a new repo without workspace."""
    tool_config = ToolConfig(registry_path=tmp_path / "repos.yml")
    repo_path = tmp_path / "new_repo"
    repo_path.mkdir()

    inspection = inspect_repo(repo_path, tool_config)

    assert inspection.exists is True
    assert inspection.has_git is False  # No .git directory
    assert inspection.workspace_path is None
    assert inspection.workspace_status == "missing"
    assert len(inspection.issues) == 0


def test_inspect_repo_with_workspace(tmp_path: Path) -> None:
    """Test inspecting a repo with existing workspace."""
    tool_config = ToolConfig(registry_path=tmp_path / "repos.yml")
    repo_path = tmp_path / "existing_repo"
    repo_path.mkdir()

    # Create workspace
    workspace_path = repo_path / ".llmc/rag"
    config_dir = workspace_path / "config"
    config_dir.mkdir(parents=True)

    # Create config files
    rag_config = config_dir / "rag.yml"
    rag_config.write_text(yaml.dump({"repo_id": "test", "display_name": "Test"}))
    version_config = config_dir / "version.yml"
    version_config.write_text(yaml.dump({"config_version": "v1"}))

    inspection = inspect_repo(repo_path, tool_config)

    assert inspection.exists is True
    assert inspection.workspace_status == "ok"
    assert inspection.workspace_path == workspace_path


def test_inspect_repo_nonexistent(tmp_path: Path) -> None:
    """Test inspecting a non-existent repo."""
    tool_config = ToolConfig(registry_path=tmp_path / "repos.yml")
    repo_path = tmp_path / "nonexistent"

    inspection = inspect_repo(repo_path, tool_config)

    assert inspection.exists is False
    assert inspection.workspace_status == "missing"
    assert len(inspection.issues) > 0


def test_workspace_plan_new(tmp_path: Path) -> None:
    """Test planning workspace for new repo."""
    tool_config = ToolConfig(registry_path=tmp_path / "repos.yml")
    repo_path = tmp_path / "planned_repo"
    repo_path.mkdir()

    inspection = RepoInspection(
        repo_root=repo_path,
        exists=True,
        has_git=True,
        workspace_path=None,
        workspace_status="missing",
    )

    plan = plan_workspace(repo_path, tool_config, inspection)

    assert plan.workspace_root == repo_path / ".llmc/rag"
    assert plan.config_dir == repo_path / ".llmc/rag/config"
    assert plan.index_dir == repo_path / ".llmc/rag/index"
    assert plan.logs_dir == repo_path / ".llmc/rag/logs"
    assert plan.tmp_dir == repo_path / ".llmc/rag/tmp"
    assert plan.rag_config_path == repo_path / ".llmc/rag/config/rag.yml"
    assert plan.version_config_path == repo_path / ".llmc/rag/config/version.yml"


def test_workspace_init_creates_directories(tmp_path: Path) -> None:
    """Test that init_workspace creates all necessary directories."""
    tool_config = ToolConfig(registry_path=tmp_path / "repos.yml")
    repo_path = tmp_path / "init_repo"
    repo_path.mkdir()

    inspection = RepoInspection(
        repo_root=repo_path,
        exists=True,
        has_git=False,
        workspace_path=None,
        workspace_status="missing",
    )

    plan = plan_workspace(repo_path, tool_config, inspection)
    init_workspace(plan, inspection, tool_config, non_interactive=True)

    # Check directories were created
    assert plan.workspace_root.exists()
    assert plan.config_dir.exists()
    assert plan.index_dir.exists()
    assert plan.enrichments_dir.exists()
    assert plan.metadata_dir.exists()
    assert plan.logs_dir.exists()
    assert plan.tmp_dir.exists()

    # Check config files were created
    assert plan.rag_config_path.exists()
    assert plan.version_config_path.exists()

    # Check gitignore was created
    gitignore = plan.workspace_root / ".gitignore"
    assert gitignore.exists()
    assert "index/" in gitignore.read_text()


def test_workspace_init_idempotent(tmp_path: Path) -> None:
    """Test that init_workspace is idempotent."""
    tool_config = ToolConfig(registry_path=tmp_path / "repos.yml")
    repo_path = tmp_path / "idempotent_repo"
    repo_path.mkdir()

    inspection = RepoInspection(
        repo_root=repo_path,
        exists=True,
        has_git=False,
        workspace_path=None,
        workspace_status="missing",
    )

    plan = plan_workspace(repo_path, tool_config, inspection)

    # First init
    init_workspace(plan, inspection, tool_config, non_interactive=True)
    first_config = plan.rag_config_path.read_text()

    # Modify config
    plan.rag_config_path.write_text("# Modified")

    # Second init (should not overwrite)
    init_workspace(plan, inspection, tool_config, non_interactive=True)

    assert "# Modified" in plan.rag_config_path.read_text()


def test_workspace_validate_ok(tmp_path: Path) -> None:
    """Test validation of a valid workspace."""
    workspace_path = tmp_path / "valid_workspace"
    config_dir = workspace_path / "config"
    config_dir.mkdir(parents=True)

    rag_config = config_dir / "rag.yml"
    rag_config.write_text(yaml.dump({"repo_id": "test"}))
    version_config = config_dir / "version.yml"
    version_config.write_text(yaml.dump({"config_version": "v1"}))

    plan = Mock()
    plan.config_dir = config_dir
    plan.rag_config_path = rag_config
    plan.version_config_path = version_config

    validation = validate_workspace(plan)

    assert validation.status == "ok"
    assert len(validation.issues) == 0


def test_workspace_validate_missing_files(tmp_path: Path) -> None:
    """Test validation with missing config files."""
    workspace_path = tmp_path / "invalid_workspace"
    config_dir = workspace_path / "config"
    config_dir.mkdir(parents=True)

    plan = Mock()
    plan.config_dir = config_dir
    plan.rag_config_path = config_dir / "rag.yml"
    plan.version_config_path = config_dir / "version.yml"

    validation = validate_workspace(plan)

    assert validation.status == "warning"
    assert len(validation.issues) > 0
    assert any("version.yml" in issue for issue in validation.issues)


def test_generate_repo_id(tmp_path: Path) -> None:
    """Test that repo IDs are consistent and based on path."""
    repo_path = tmp_path / "test_repo"

    id1 = generate_repo_id(repo_path)
    id2 = generate_repo_id(repo_path)

    # Should be deterministic
    assert id1 == id2

    # Should start with 'repo-'
    assert id1.startswith("repo-")

    # Should be different for different paths
    other_repo = tmp_path / "other_repo"
    id3 = generate_repo_id(other_repo)
    assert id1 != id3


def test_notify_refresh_creates_flag(tmp_path: Path) -> None:
    """Test that notify_refresh creates a refresh flag."""
    control_dir = tmp_path / "control"
    tool_config = ToolConfig(
        registry_path=tmp_path / "repos.yml",
        daemon_control_path=control_dir,
    )

    entry = RegistryEntry(
        repo_id="repo-test",
        repo_path=tmp_path / "test",
        rag_workspace_path=tmp_path / "test" / ".llmc/rag",
        display_name="Test",
        rag_profile="default",
    )

    notify_refresh(entry, tool_config)

    flag_path = control_dir / "refresh_repo-test.flag"
    assert flag_path.exists()


def test_notify_refresh_all_creates_flag(tmp_path: Path) -> None:
    """Test that notify_refresh_all creates a refresh_all flag."""
    control_dir = tmp_path / "control"
    tool_config = ToolConfig(
        registry_path=tmp_path / "repos.yml",
        daemon_control_path=control_dir,
    )

    notify_refresh_all(tool_config)

    flag_path = control_dir / "refresh_all.flag"
    assert flag_path.exists()


def test_notify_refresh_no_control_path(tmp_path: Path) -> None:
    """Test that notify_refresh handles missing control path gracefully."""
    tool_config = ToolConfig(
        registry_path=tmp_path / "repos.yml",
        daemon_control_path=None,
    )

    entry = RegistryEntry(
        repo_id="repo-test",
        repo_path=tmp_path / "test",
        rag_workspace_path=tmp_path / "test" / ".llmc/rag",
        display_name="Test",
        rag_profile="default",
    )

    # Should not raise exception
    notify_refresh(entry, tool_config)


def test_canonical_repo_path(tmp_path: Path) -> None:
    """Test canonical path resolution."""
    repo_path = tmp_path / "nested" / "repo"
    repo_path.mkdir(parents=True)

    canonical = canonical_repo_path(repo_path)

    assert canonical.is_absolute()
    assert canonical == repo_path.resolve()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
