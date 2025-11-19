from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from .archive import create_snapshot_tar
from .cli import clean_workspace, resolve_export_dir, resolve_workspace_from_cli
from .doctor import doctor_paths


def doctor_paths_cmd(repo_root: Path, workspace: str | None, export: str | None) -> Dict[str, Any]:
    return doctor_paths(repo_root, workspace, export)


def snapshot_workspace_cmd(
    repo_root: Path,
    workspace: str | None,
    export: str | None,
    name: str | None,
    include_hidden: bool,
    force: bool,
) -> Dict[str, Any]:
    ws_root = resolve_workspace_from_cli(repo_root, workspace)
    export_dir = resolve_export_dir(repo_root, workspace, export or "exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    if name is None:
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        name = f"snapshot-{ts}.tar.gz"
    out_rel = str(Path(export_dir) / name)
    tar_path = create_snapshot_tar(fs=SafeFS(ws_root), root_rel=".", out_rel=out_rel, include_hidden=include_hidden, force=force)
    return {"snapshot": tar_path}


def clean_workspace_cmd(repo_root: Path, workspace: str | None = None, force: bool = False) -> Dict[str, Any]:
    return clean_workspace(repo_root, workspace, force=force)


def _coerce(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _coerce(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_coerce(v) for v in obj]
    return obj


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llmc-cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_doc = sub.add_parser("doctor-paths", help="Quick path sanity check")
    p_doc.add_argument("--repo", required=True)
    p_doc.add_argument("--workspace", default=None)
    p_doc.add_argument("--export", default=None)
    p_doc.add_argument("--json", action="store_true")

    p_snap = sub.add_parser("snapshot", help="Create workspace snapshot tar.gz")
    p_snap.add_argument("--repo", required=True)
    p_snap.add_argument("--workspace", default=None)
    p_snap.add_argument("--export", default=None)
    p_snap.add_argument("--name", default=None)
    p_snap.add_argument("--include-hidden", action="store_true")
    p_snap.add_argument("--force", action="store_true")
    p_snap.add_argument("--json", action="store_true")

    p_clean = sub.add_parser("clean", help="Clean workspace contents (requires --force)")
    p_clean.add_argument("--repo", required=True)
    p_clean.add_argument("--workspace", default=None)
    p_clean.add_argument("--force", action="store_true")
    p_clean.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "doctor-paths":
            out = doctor_paths_cmd(Path(args.repo), args.workspace, args.export)
        elif args.cmd == "snapshot":
            out = snapshot_workspace_cmd(
                Path(args.repo),
                args.workspace,
                args.export,
                args.name,
                args.include_hidden,
                args.force,
            )
        elif args.cmd == "clean":
            out = clean_workspace_cmd(Path(args.repo), args.workspace, args.force)
        else:
            raise RuntimeError(f"Unknown command: {args.cmd}")

        if getattr(args, "json", False):
            print(json.dumps(_coerce(out), default=str))
        else:
            print(out)
        return 0
    except Exception as exc:  # noqa: BLE001
        # Map known user errors to exit code 2
        name = exc.__class__.__name__
        known = {"PathTraversalError", "PathPolicyError", "RuntimeError", "FileExistsError"}
        if name in known:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"ERROR: {name}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

