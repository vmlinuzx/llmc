from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Callable, Generator, Iterable, Iterator, List, Optional, Set, Tuple

from .config import get_exclude_dirs
from .lang import is_supported, language_for_path


def find_repo_root(start: Optional[Path] = None) -> Path:
    start = start or Path.cwd()
    current = start.resolve()
    for ancestor in [current, *current.parents]:
        if (ancestor / ".git").exists():
            return ancestor
    return start


def iter_source_files(repo_root: Path, include_paths: Optional[Iterable[Path]] = None) -> Iterator[Path]:
    matcher = _gitignore_matcher(repo_root)
    if include_paths:
        for path in include_paths:
            absolute = (repo_root / path).resolve()
            try:
                rel = absolute.relative_to(repo_root)
            except ValueError:
                continue
            if matcher(rel):
                continue
            if absolute.is_dir():
                yield from _iter_directory(repo_root, absolute, matcher)
            elif absolute.is_file() and is_supported(rel):
                yield rel
    else:
        yield from _iter_directory(repo_root, repo_root, matcher)


def _iter_directory(repo_root: Path, directory: Path, matcher: Callable[[Path], bool]) -> Iterator[Path]:
    exclude_dirs = get_exclude_dirs(repo_root)
    for root, dirs, files in os.walk(directory):
        root_path = Path(root)
        pruned_dirs = []
        for name in dirs:
            if name in exclude_dirs:
                continue
            candidate = (root_path / name).relative_to(repo_root)
            if matcher(candidate):
                continue
            pruned_dirs.append(name)
        dirs[:] = pruned_dirs
        for file in files:
            rel = (root_path / file).relative_to(repo_root)
            if matcher(rel):
                continue
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


def _load_additional_ignores(repo_root: Path) -> list[str]:
    """Load extra ignore globs from .ragignore and env (LLMC_RAG_EXCLUDE).

    Patterns are matched against POSIX-style repo-relative paths (e.g.,
    "DOCS/*.md", "tools/**", "AGENTS.md").
    """
    patterns: list[str] = []
    env_raw = os.getenv("LLMC_RAG_EXCLUDE", "").strip()
    if env_raw:
        for part in env_raw.split(","):
            pat = part.strip()
            if pat:
                patterns.append(pat)
    cfg = repo_root / ".ragignore"
    if cfg.exists():
        try:
            for line in cfg.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                patterns.append(line)
        except OSError:
            pass
    return patterns


def _gitignore_matcher(repo_root: Path) -> Callable[[Path], bool]:
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return lambda _: False

    resolved_root = repo_root.resolve()

    @lru_cache(maxsize=8192)
    def _is_ignored(rel_path: str) -> bool:
        if not rel_path:
            return False
        try:
            result = subprocess.run(
                ["git", "check-ignore", "-q", rel_path],
                cwd=resolved_root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except FileNotFoundError:
            return False
        return result.returncode == 0

    extra_patterns = _load_additional_ignores(resolved_root)

    @lru_cache(maxsize=8192)
    def _matches_extra(rel_path: str) -> bool:
        if not extra_patterns:
            return False
        # Normalize to POSIX-style
        path = rel_path
        for pat in extra_patterns:
            # Support simple directory prefixes without globs
            if pat.endswith("/") and (path == pat[:-1] or path.startswith(pat)):
                return True
            if fnmatchcase(path, pat):
                return True
        return False

    def matcher(path: Path) -> bool:
        rel = path.as_posix()
        return _is_ignored(rel) or _matches_extra(rel)

    return matcher
