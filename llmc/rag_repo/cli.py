"""CLI entrypoint for `llmc-rag-repo`."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import load_tool_config
from .configurator import RepoConfigurator
from .fs import SafeFS
from .inspect_repo import inspect_repo
from .models import RegistryEntry
from .notifier import notify_refresh
from .registry import RegistryAdapter
from .utils import canonical_repo_path, generate_repo_id, safe_subpath
from .workspace import init_workspace, plan_workspace, validate_workspace


def resolve_workspace_from_cli(
    repo_root: Path,
    workspace_arg: str | Path | None = None,
    default_name: str = ".llmc/workspace",
) -> Path:
    """
    Resolve workspace path from CLI args with path safety enforcement.

    - Normalizes repo_root via canonical_repo_path.
    - If workspace_arg is None, uses default_name.
    - Uses safe_subpath to ensure the workspace stays under the repo root.
    """
    base = canonical_repo_path(repo_root)
    name_or_path = workspace_arg if workspace_arg is not None else default_name
    return safe_subpath(base, name_or_path)


def clean_workspace(
    repo_root: Path, workspace_arg: str | Path | None = None, *, force: bool = False
) -> dict:
    """Remove contents of a workspace safely. Requires force=True."""
    if not force:
        raise RuntimeError(
            "Refusing to clean without --force. This operation is destructive."
        )
    ws_root = resolve_workspace_from_cli(repo_root, workspace_arg)
    fs = SafeFS(ws_root)
    fs.rm_tree(".")
    return {"workspace_root": ws_root}


def resolve_export_dir(
    repo_root: Path,
    workspace_arg: str | Path | None = None,
    export_arg: str | Path | None = None,
    default_subdir: str = "exports",
) -> Path:
    """Ensure export directory is under the workspace root."""
    ws_root = resolve_workspace_from_cli(repo_root, workspace_arg)
    candidate = export_arg if export_arg is not None else default_subdir
    return safe_subpath(ws_root, candidate)


def export_bundle(
    repo_root: Path,
    workspace_arg: str | Path | None = None,
    export_arg: str | Path | None = None,
    *,
    force: bool = False,
) -> dict:
    """
    Prepare an export directory with overwrite guard.

    This function only handles path safety and overwrite checks; the actual
    bundle creation is wired elsewhere.
    """
    export_dir = resolve_export_dir(repo_root, workspace_arg, export_arg)
    export_dir.mkdir(parents=True, exist_ok=True)
    if any(export_dir.iterdir()) and not force:
        raise RuntimeError(
            "Export directory is not empty. Re-run with --force to overwrite."
        )
    return {"export_dir": export_dir}


def _print_top_level_help() -> None:
    """Print a tree-style help overview for llmc-rag-repo."""
    print(
        "LLMC RAG Repo Tool\n\n"
        "Manage which repos are tracked by the LLMC RAG daemon.\n\n"
        "Usage:\n"
        "  llmc-rag-repo <command> [options]\n\n"
        "Commands:\n"
        "  add        Register a repo and create its .llmc/rag workspace\n"
        "  remove     Unregister a repo\n"
        "  list       List all registered repos\n"
        "  inspect    Show detailed info for a single repo\n"
        "  help       Show this help overview\n\n"
        "Examples:\n"
        "  llmc-rag-repo add /home/you/src/llmc\n"
        "  llmc-rag-repo list\n"
        "  llmc-rag-repo inspect /home/you/src/llmc\n"
    )


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # No args or explicit --help/-h: show friendly overview instead of
    # argparse's "the following arguments are required" error.
    if not argv or argv[0] in ("-h", "--help"):
        _print_top_level_help()
        return 0

    parser = argparse.ArgumentParser(description="LLMC RAG Repo Registration Tool")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Register or re-register a repo for RAG")
    p_add.add_argument("path", help="Path to repo (default: .)", nargs="?", default=".")
    p_add.add_argument("--config", help="Path to tool config", default=None)
    p_add.add_argument(
        "--template", help="Path to custom llmc.toml template", default=None
    )
    p_add.add_argument("-y", "--yes", action="store_true", help="Assume yes to prompts")
    p_add.add_argument("--json", action="store_true", help="JSON output")

    p_remove = sub.add_parser("remove", help="Unregister a repo from the registry")
    p_remove.add_argument("target", help="Repo path or repo_id")
    p_remove.add_argument("--config", help="Path to tool config", default=None)

    p_list = sub.add_parser("list", help="List registered repos")
    p_list.add_argument("--config", help="Path to tool config", default=None)
    p_list.add_argument("--json", action="store_true", help="JSON output")

    p_inspect = sub.add_parser("inspect", help="Inspect a repo and its registry entry")
    p_inspect.add_argument("target", help="Repo path or repo_id")
    p_inspect.add_argument("--config", help="Path to tool config", default=None)
    p_inspect.add_argument("--json", action="store_true", help="JSON output")

    sub.add_parser("help", help="Show a tree-style help overview")

    args = parser.parse_args(argv)
    if args.command == "help":
        _print_top_level_help()
        return 0

    tool_config = load_tool_config(getattr(args, "config", None))
    registry = RegistryAdapter(tool_config)

    if args.command == "add":
        return _cmd_add(args, tool_config, registry)
    if args.command == "remove":
        return _cmd_remove(args, tool_config, registry)
    if args.command == "list":
        return _cmd_list(args, tool_config, registry)
    if args.command == "inspect":
        return _cmd_inspect(args, tool_config, registry)

    parser.error("Unknown command")
    return 1


def cli(argv: list[str] | None = None) -> int:
    """
    Legacy-compatible entry point exported as `tools.rag_repo.cli`.

    Thin wrapper around `main` so tests and external tools that imported
    `cli` continue to work.
    """
    return main(argv)


def _cmd_add(args, tool_config, registry: RegistryAdapter | None) -> int:
    if registry is None:
        registry = RegistryAdapter(tool_config)

    repo_path = canonical_repo_path(Path(args.path))

    try:
        inspection = inspect_repo(repo_path, tool_config)
        if not inspection.exists:
            print(f"Error: repo path does not exist: {repo_path}")
            return 1

        plan = plan_workspace(repo_path, tool_config, inspection)
        init_workspace(plan, inspection, tool_config, non_interactive=args.yes)
        validation = validate_workspace(plan)
    except PermissionError as exc:
        # Common case: attempting to register a repo under a protected path
        # like /root without sufficient privileges.
        print(
            f"Permission denied while accessing {repo_path}: {exc}. "
            "Use a repo you own or adjust permissions.",
            file=sys.stderr,
        )
        return 1

    if validation.status == "error":
        print("Workspace validation failed:")
        for issue in validation.issues:
            print(f"- {issue}")
        return 1

    repo_id = generate_repo_id(repo_path)
    entry = RegistryEntry(
        repo_id=repo_id,
        repo_path=repo_path,
        rag_workspace_path=plan.workspace_root,
        display_name=inspection.repo_root.name,
        rag_profile=tool_config.default_rag_profile,
    )
    registry.register(entry)
    notify_refresh(entry, tool_config)

    # Repo Configurator Integration
    configurator = RepoConfigurator(interactive=not args.yes)
    configurator.configure(repo_path=repo_path, template_path=args.template)

    if args.json:
        import json

        print(
            json.dumps(
                {
                    "repo_id": entry.repo_id,
                    "repo_path": str(entry.repo_path),
                    "rag_workspace_path": str(entry.rag_workspace_path),
                    "display_name": entry.display_name,
                }
            )
        )
    else:
        print(f"Registered repo {entry.display_name} ({entry.repo_id})")
        print(f"  Repo path: {entry.repo_path}")
        print(f"  Workspace: {entry.rag_workspace_path}")

    return 0


def _cmd_remove(args, tool_config, registry: RegistryAdapter) -> int:
    target = args.target
    entry = None
    if target.startswith("repo-"):
        entry = registry.find_by_id(target)
    else:
        entry = registry.find_by_path(Path(target))

    if entry is None:
        print(f"Repo not found in registry: {target}")
        return 1

    ok = registry.unregister_by_id(entry.repo_id)
    if ok:
        print(f"Unregistered repo {entry.display_name} ({entry.repo_id})")
        return 0

    print(f"Failed to unregister repo {entry.repo_id}")
    return 1


def _cmd_list(args, tool_config, registry: RegistryAdapter) -> int:
    entries = registry.list_entries()
    if args.json:
        import json

        payload = [
            {
                "repo_id": e.repo_id,
                "display_name": e.display_name,
                "repo_path": str(e.repo_path),
                "rag_workspace_path": str(e.rag_workspace_path),
                "rag_profile": e.rag_profile,
            }
            for e in entries
        ]
        print(json.dumps(payload, indent=2))
        return 0

    if not entries:
        print("No repos registered.")
        return 0

    for e in entries:
        print(f"{e.repo_id}  {e.display_name}")
        print(f"  repo: {e.repo_path}")
        print(f"  workspace: {e.rag_workspace_path}")
    return 0


def _cmd_inspect(args, tool_config, registry: RegistryAdapter) -> int:
    target = args.target
    entry = None
    if target.startswith("repo-"):
        entry = registry.find_by_id(target)
        repo_root = entry.repo_path if entry else Path(".")
    else:
        repo_root = canonical_repo_path(Path(target))
        entry = registry.find_by_path(repo_root)

    inspection = inspect_repo(repo_root, tool_config)

    data = {
        "repo_root": str(inspection.repo_root),
        "exists": inspection.exists,
        "has_git": inspection.has_git,
        "workspace_path": str(inspection.workspace_path or ""),
        "workspace_status": inspection.workspace_status,
        "issues": inspection.issues,
        "registry_entry": None,
    }

    if entry:
        data["registry_entry"] = {
            "repo_id": entry.repo_id,
            "repo_path": str(entry.repo_path),
            "rag_workspace_path": str(entry.rag_workspace_path),
            "display_name": entry.display_name,
            "rag_profile": entry.rag_profile,
        }

    if args.json:
        import json

        print(json.dumps(data, indent=2))
    else:
        print(f"Repo root: {data['repo_root']}")
        print(f"  Exists: {data['exists']}  Git: {data['has_git']}")
        print(f"  Workspace: {data['workspace_path']} ({data['workspace_status']})")
        if data["issues"]:
            print("  Issues:")
            for issue in data["issues"]:
                print(f"    - {issue}")
        if data["registry_entry"]:
            print("  Registry:")
            re = data["registry_entry"]
            print(f"    repo_id: {re['repo_id']}")
            print(f"    display_name: {re['display_name']}")
            print(f"    rag_profile: {re['rag_profile']}")
        else:
            print("  Registry: <no entry>")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
