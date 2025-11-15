"""CLI entrypoint for `llmc-rag-repo`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .config import load_tool_config
from .inspect_repo import inspect_repo
from .models import RegistryEntry
from .notifier import notify_refresh
from .registry import RegistryAdapter
from .workspace import init_workspace, plan_workspace, validate_workspace
from .utils import canonical_repo_path, generate_repo_id


def _print_top_level_help() -> None:
    """Print a tree-style help overview for llmc-rag-repo."""
    print(
        (
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
    )


def main(argv: Optional[list[str]] = None) -> int:
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


def _cmd_add(args, tool_config, registry: RegistryAdapter) -> int:
    repo_path = canonical_repo_path(Path(args.path))
    inspection = inspect_repo(repo_path, tool_config)
    if not inspection.exists:
        print(f"Error: repo path does not exist: {repo_path}")
        return 1

    plan = plan_workspace(repo_path, tool_config, inspection)
    init_workspace(plan, inspection, tool_config, non_interactive=args.yes)
    validation = validate_workspace(plan)
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
