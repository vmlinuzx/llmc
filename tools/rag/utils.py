from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

from .lang import is_supported, language_for_path

EXCLUDE_DIRS = {".git", ".rag", "node_modules", "dist", "build", "__pycache__", ".venv"}


def find_repo_root(start: Optional[Path] = None) -> Path:
    start = start or Path.cwd()
    current = start.resolve()
    for ancestor in [current, *current.parents]:
        if (ancestor / ".git").exists():
            return ancestor
    return start


def iter_source_files(repo_root: Path, include_paths: Optional[Iterable[Path]] = None) -> Iterator[Path]:
    if include_paths:
        for path in include_paths:
            absolute = (repo_root / path).resolve()
            if absolute.is_dir():
                yield from _iter_directory(repo_root, absolute)
            elif absolute.is_file():
                rel = absolute.relative_to(repo_root)
                if is_supported(rel):
                    yield rel
    else:
        yield from _iter_directory(repo_root, repo_root)


def _iter_directory(repo_root: Path, directory: Path) -> Iterator[Path]:
    for root, dirs, files in os.walk(directory):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            rel = (root_path / file).relative_to(repo_root)
            if is_supported(rel):
                yield rel


def git_commit_sha(repo_root: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def git_changed_paths(repo_root: Path, since: str) -> List[Path]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", since, "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        paths = []
        for line in result.stdout.splitlines():
            candidate = Path(line.strip())
            if candidate.suffix and is_supported(candidate):
                paths.append(candidate)
        return paths
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def language_from_path(path: Path) -> Optional[str]:
    return language_for_path(path)
