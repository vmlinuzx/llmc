from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from .policy import PathPolicyError, PathSafetyPolicy, enforce_policy
from .utils import safe_subpath


@dataclass
class SafeFS:
    """Filesystem adapter that constrains all operations under a base directory."""

    base: Path
    policy: PathSafetyPolicy | None = None

    def __post_init__(self) -> None:
        self.base = Path(self.base).expanduser().resolve()

    def resolve(self, user_path: str | Path) -> Path:
        """Resolve a user-controlled path under the base using safe_subpath + policy."""
        path = safe_subpath(self.base, user_path)
        if self.policy is not None:
            path = enforce_policy(path, self.policy)
        return path

    def open_read(self, user_path: str | Path):
        """Open a file for reading (binary) under the base."""
        path = self.resolve(user_path)
        return open(path, "rb")

    def open_write(self, user_path: str | Path, *, exist_ok_parent: bool = True):
        """
        Open a file for writing (binary) under the base.

        When exist_ok_parent is True, ensure the parent directory exists.
        """
        if self.policy is not None:
            if self.policy.readonly:
                raise PathPolicyError("Readonly policy prevents write")
            if self.policy.dry_run:
                raise PathPolicyError("Dry-run policy prevents write")

        path = self.resolve(user_path)
        if exist_ok_parent:
            path.parent.mkdir(parents=True, exist_ok=True)
        return open(path, "wb")

    def mkdir_p(self, user_path: str | Path) -> Path:
        """Create a directory (and parents) under the base."""
        if self.policy is not None and self.policy.readonly:
            raise PathPolicyError("Readonly policy prevents mkdir")

        path = self.resolve(user_path)
        if self.policy is not None and self.policy.dry_run:
            # In dry-run mode, report the path but do not create it.
            return path

        path.mkdir(parents=True, exist_ok=True)
        return path

    def list_dir(self, user_path: str | Path = ".") -> list[Path]:
        """List entries for a directory under the base; empty if it does not exist."""
        path = self.resolve(user_path)
        if not path.exists():
            return []
        return list(path.iterdir())

    def rm_tree(self, user_path: str | Path):
        """
        Recursively delete a path under the base.

        If the resolved path is exactly the base, delete only its children
        (leaving the base directory itself intact).
        """
        if self.policy is not None and self.policy.readonly:
            raise PathPolicyError("Readonly policy prevents delete")

        path = self.resolve(user_path)

        if self.policy is not None and self.policy.dry_run:
            summary: dict[str, list[str] | str] = {"path": str(path), "would_delete": []}
            if path.exists():
                summary["would_delete"] = [str(child) for child in path.iterdir()]
            return summary

        if path == self.base:
            for child in list(path.iterdir()):
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    try:
                        child.unlink()
                    except FileNotFoundError:
                        pass
            return

        if path.is_dir():
            shutil.rmtree(path)
        else:
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def copy_into(self, src_rel: str | Path, dst_rel: str | Path, *, overwrite: bool = False):
        """Copy file/dir inside base with policy + overwrite support."""
        src = self.resolve(src_rel)
        dst = self.resolve(dst_rel)
        if self.policy is not None and self.policy.readonly:
            raise PathPolicyError("Readonly policy prevents copy")
        if self.policy is not None and self.policy.dry_run:
            return {"op": "copy", "src": str(src), "dst": str(dst)}
        if dst.exists() and not overwrite:
            raise FileExistsError(dst)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=overwrite)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return dst

    def move_into(self, src_rel: str | Path, dst_rel: str | Path, *, overwrite: bool = False):
        """Move file/dir inside base with policy + overwrite support."""
        src = self.resolve(src_rel)
        dst = self.resolve(dst_rel)
        if self.policy is not None and self.policy.readonly:
            raise PathPolicyError("Readonly policy prevents move")
        if self.policy is not None and self.policy.dry_run:
            return {"op": "move", "src": str(src), "dst": str(dst)}
        if dst.exists() and not overwrite:
            raise FileExistsError(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        return Path(shutil.move(str(src), str(dst)))
