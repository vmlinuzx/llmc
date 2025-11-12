#!/usr/bin/env python3
"""
Create a repository context ZIP that honors .gitignore.

Output filename: llmccontextMMDDYYHHSS.zip (UTC time)
Destination directory: parent of repo root (../ relative to repo root)

Requirements:
- Python 3.8+
- Git available on PATH (uses `git ls-files -co --exclude-standard`).
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
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
    # Prefer git's view of the top-level, with a manual fallback.
    rc, out, _ = _run(["git", "rev-parse", "--show-toplevel"], cwd=start)
    if rc == 0 and out.strip():
        return Path(out.strip())
    # Fallback: walk up until we see a .git directory.
    cur = start.resolve()
    for parent in [cur] + list(cur.parents):
        if (parent / ".git").exists():
            return parent
    # If not found, default to start (will likely fail later when using git).
    return start


def list_included_paths(repo_root: Path) -> list[Path]:
    """Return files that are tracked or untracked-but-not-ignored.

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
        p = (repo_root / rel).resolve()
        # Only include regular files; skip directories or things that vanished.
        if p.is_file():
            paths.append(p)
    return paths


def build_zip_name() -> str:
    # UTC; format MMDDYYHHSS — note no minutes per request.
    ts = datetime.now(timezone.utc).strftime("%m%d%y%H%S")
    return f"llmccontext{ts}.zip"


def main() -> int:
    script_path = Path(__file__).resolve()
    repo_root = find_repo_root(script_path.parent)

    # Destination is parent of repo root (e.g., ~/src)
    dest_dir = repo_root.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    zip_name = build_zip_name()
    zip_path = dest_dir / zip_name

    # Collect file list honoring .gitignore via git
    files = list_included_paths(repo_root)
    if not files:
        print("No files to include. Is this a git repo?", file=sys.stderr)
        return 3

    # Write archive with paths relative to repo root
    try:
        with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for abs_path in files:
                try:
                    rel = abs_path.relative_to(repo_root)
                except ValueError:
                    # If for some reason it's outside root, skip it.
                    continue
                zf.write(abs_path, arcname=str(rel))
    except PermissionError as e:
        print(f"Permission denied creating {zip_path}: {e}", file=sys.stderr)
        print(
            "Hint: run from a context that can write to the parent directory, or adjust destination.",
            file=sys.stderr,
        )
        return 4

    print(f"Created: {zip_path}")
    print(f"Files included: {len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
