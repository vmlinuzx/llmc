from __future__ import annotations

import tarfile

from .fs import SafeFS
from .policy import PathPolicyError


def create_snapshot_tar(
    fs: SafeFS,
    root_rel: str = ".",
    out_rel: str = "exports/snapshot.tar.gz",
    *,
    include_hidden: bool = False,
    force: bool = False,
):
    """
    Create a gzipped tar snapshot of workspace contents.

    Returns the absolute output path (Path). Honors fs.policy readonly/dry_run.
    """
    if fs.policy is not None and fs.policy.readonly:
        raise PathPolicyError("Readonly policy prevents snapshot writes")

    root = fs.resolve(root_rel)
    out_path = fs.resolve(out_rel)

    if fs.policy is not None and fs.policy.dry_run:
        return {"op": "snapshot", "root": str(root), "out": str(out_path)}

    if out_path.exists() and not force:
        raise FileExistsError(out_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(out_path, "w:gz") as tar:
        for path in root.rglob("*"):
            rel = path.relative_to(root)
            if not include_hidden and any(part.startswith(".") for part in rel.parts):
                continue
            tar.add(path, arcname=str(rel))

    return out_path

