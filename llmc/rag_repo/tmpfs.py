from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import uuid

from .utils import safe_subpath


@dataclass
class SafeTmp:
    """
    Helper for creating temporary work directories inside a workspace root.

    Ensures all temporary directories live under the given workspace root,
    never under system-wide /tmp.
    """

    workspace_root: Path
    subdir: str = ".tmp"

    def base(self) -> Path:
        root = Path(self.workspace_root).expanduser().resolve()
        return safe_subpath(root, self.subdir)

    def make(self, prefix: str = "job") -> Path:
        root = self.base()
        root.mkdir(parents=True, exist_ok=True)
        name = f"{prefix}-{uuid.uuid4().hex}"
        tmp_path = safe_subpath(root, name)
        tmp_path.mkdir(parents=True, exist_ok=False)
        return tmp_path

    def cleanup(self, path: Path) -> None:
        path = Path(path).expanduser().resolve()
        tmp_root = self.base()
        # Ensure path is under the temporary root; ValueError if outside.
        _ = path.relative_to(tmp_root)
        shutil.rmtree(path, ignore_errors=True)
