from pathlib import Path

from tools.rag_repo.models import ToolConfig
from tools.rag_repo.inspect_repo import inspect_repo
from tools.rag_repo.workspace import init_workspace, plan_workspace, validate_workspace


def test_workspace_init_and_validate(tmp_path: Path) -> None:
    repo_root = tmp_path / "my_repo"
    repo_root.mkdir()

    cfg = ToolConfig(registry_path=tmp_path / "registry.yml")
    inspection = inspect_repo(repo_root, cfg)
    plan = plan_workspace(repo_root, cfg, inspection)
    init_workspace(plan, inspection, cfg, non_interactive=True)
    validation = validate_workspace(plan)

    assert validation.status == "ok"
    assert plan.rag_config_path.exists()
    assert plan.version_config_path.exists()
