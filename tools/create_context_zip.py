#!/usr/bin/env python3
"""
Create a repository context ZIP that honors .gitignore.

Output filename: <folder>.zip (in parent directory of repo root)
 - If the file already exists, add a numeric suffix: <folder>-1.zip, -2.zip, ...
Destination directory: parent of repo root (../ relative to repo root)

Requirements:
- Python 3.8+
- Git available on PATH (uses `git ls-files -co --exclude-standard`).
"""

from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
import zipfile


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate()
    return proc.returncode, out, err


def find_repo_root(start: Path) -> Path:
    """Return the repository root using git, with a manual fallback."""
    rc, out, _ = _run(["git", "rev-parse", "--show-toplevel"], cwd=start)
    if rc == 0 and out.strip():
        return Path(out.strip())
    cur = start.resolve()
    for parent in [cur] + list(cur.parents):
        if (parent / ".git").exists():
            return parent
    return start


def list_included_paths(repo_root: Path) -> list[Path]:
    """Files that are tracked or untracked-but-not-ignored.

    Uses: git ls-files -co --exclude-standard
    -c / --cached -> tracked files
    -o / --others -> untracked files
    --exclude-standard -> honors .gitignore, .git/info/exclude, core.excludesFile
    """
    rc, out, err = _run(["git", "ls-files", "-co", "--exclude-standard"], cwd=repo_root)
    if rc != 0:
        print("Error: failed to list files with git:", err.strip() or rc, file=sys.stderr)
        sys.exit(2)
    rel_paths = [line.strip() for line in out.splitlines() if line.strip()]
    paths: list[Path] = []
    for rel in rel_paths:
        # Preserve original path (do not .resolve()) to avoid collapsing hard/symlinks
        p = repo_root / rel
        if p.is_file():
            paths.append(p)
    return paths


def next_available_zip_path(dest_dir: Path, base_name: str) -> Path:
    """Return a zip path <base_name>.zip or with -N suffix if exists."""
    candidate = dest_dir / f"{base_name}.zip"
    if not candidate.exists():
        return candidate
    n = 1
    while True:
        alt = dest_dir / f"{base_name}-{n}.zip"
        if not alt.exists():
            return alt
        n += 1


def main() -> int:
    repo_root = find_repo_root(Path.cwd())

    # Destination is parent of repo root (e.g., ~/src)
    dest_dir = repo_root.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # New base name includes repo name and timestamp
    base_zip_name = f"{repo_root.name}-{timestamp}"

    zip_path = next_available_zip_path(dest_dir, base_zip_name)

    files = list_included_paths(repo_root)
    if not files:
        print("No files to include. Is this a git repo?", file=sys.stderr)
        return 3

    # Write archive with paths relative to repo root; skip duplicate arcnames
    try:
        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            seen: set[str] = set()
            for abs_path in files:
                try:
                    rel = abs_path.relative_to(repo_root)
                except ValueError:
                    continue
                arcname = str(rel)
                if arcname in seen:
                    continue
                seen.add(arcname)
                stat = abs_path.stat()
                zinfo = zipfile.ZipInfo(filename=arcname)
                # ZIP format cannot handle dates before 1980
                zt = time.gmtime(stat.st_mtime)[:6]
                if zt[0] < 1980:
                    zt = (1980, 1, 1, 0, 0, 0)
                zinfo.date_time = zt
                with open(abs_path, "rb") as src:
                    zf.writestr(zinfo, src.read())
    except PermissionError as e:
        print(f"Permission denied creating {zip_path}: {e}", file=sys.stderr)
        print("Hint: run from a context that can write to the parent directory, or adjust destination.", file=sys.stderr)
        return 4

    print(f"Created: {zip_path}")
    print(f"Files included: {len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

