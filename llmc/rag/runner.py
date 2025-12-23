from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from .config import index_path_for_write
from llmc.core import find_repo_root
from .lang import EXTENSION_LANG

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_SUFFIXES = {ext.lower() for ext in EXTENSION_LANG.keys()}
DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".rag",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".venv",
}


def log(msg: str) -> None:
    logger.info(msg)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cached_hashes(index_path: Path) -> dict[str, str]:
    """Load cached file hashes for backwards compatibility."""
    if not index_path.exists():
        return {}
    conn = sqlite3.connect(index_path)
    try:
        rows = conn.execute("SELECT path, file_hash FROM files")
        return {row[0]: row[1] for row in rows}
    finally:
        conn.close()


def load_cached_file_meta(index_path: Path) -> dict[str, tuple[str, float, int]]:
    """Load cached file metadata (hash, mtime, size) for smart change detection.
    
    Returns dict mapping path -> (file_hash, mtime, size)
    This allows mtime/size filtering BEFORE expensive SHA256 hashing.
    """
    if not index_path.exists():
        return {}
    conn = sqlite3.connect(index_path)
    try:
        rows = conn.execute("SELECT path, file_hash, mtime, size FROM files")
        return {row[0]: (row[1], row[2] or 0.0, row[3] or 0) for row in rows}
    finally:
        conn.close()


def _extra_patterns(repo_root: Path) -> list[str]:
    patterns: list[str] = []
    env_raw = os.getenv("LLMC_RAG_EXCLUDE", "").strip()
    if env_raw:
        for part in env_raw.split(","):
            pat = part.strip()
            if pat:
                patterns.append(pat)
    ragignore = repo_root / ".ragignore"
    if ragignore.exists():
        try:
            for line in ragignore.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                patterns.append(line)
        except OSError:
            pass
    return patterns


def _matches_extra(path: str, patterns: Iterable[str]) -> bool:
    for pat in patterns:
        if pat.endswith("/"):
            stem = pat[:-1]
            if path == stem or path.startswith(f"{stem}/"):
                return True
        if fnmatch(path, pat):
            return True
    return False


def fnmatch(path: str, pattern: str) -> bool:
    from fnmatch import fnmatchcase

    return fnmatchcase(path, pattern)


def iter_repo_files(repo_root: Path) -> Iterable[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-c", "-o", "--exclude-standard", "-z"],
            cwd=repo_root,
            capture_output=True,
            check=True,
        )
        output = result.stdout.decode("utf-8", errors="ignore")
        for entry in output.split("\0"):
            if entry:
                yield Path(entry)
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    for root, dirs, files in os.walk(repo_root):
        root_path = Path(root)
        rel_root = root_path.relative_to(repo_root)
        if rel_root.parts and rel_root.parts[0] in DEFAULT_EXCLUDE_DIRS:
            continue
        pruned = []
        for name in dirs:
            if name in DEFAULT_EXCLUDE_DIRS:
                continue
            pruned.append(name)
        dirs[:] = pruned
        for file in files:
            rel = (root_path / file).relative_to(repo_root)
            yield rel


def current_hashes(repo_root: Path, extra_patterns: list[str]) -> dict[str, str]:
    """Legacy: hash all files unconditionally. Use current_hashes_smart for perf."""
    hashes: dict[str, str] = {}
    for rel_path in iter_repo_files(repo_root):
        suffix = rel_path.suffix.lower()
        if suffix and suffix not in SUPPORTED_SUFFIXES:
            continue
        posix = rel_path.as_posix()
        if _matches_extra(posix, extra_patterns):
            continue
        absolute = repo_root / rel_path
        if not absolute.is_file():
            continue
        try:
            hashes[posix] = sha256_file(absolute)
        except OSError:
            continue
    return hashes


def current_hashes_smart(
    repo_root: Path,
    extra_patterns: list[str],
    cached_meta: dict[str, tuple[str, float, int]],
) -> dict[str, str]:
    """Smart change detection: only SHA256 files whose mtime/size changed.
    
    Performance optimization: uses filesystem metadata as fast filter before
    expensive hash computation. For unchanged repos, this is 10-100x faster.
    
    Args:
        repo_root: Repository root path
        extra_patterns: Patterns to exclude from indexing
        cached_meta: Dict mapping path -> (hash, mtime, size) from load_cached_file_meta()
    
    Returns:
        Dict mapping path -> current file hash
    """
    hashes: dict[str, str] = {}
    hashed_count = 0
    skipped_count = 0
    
    for rel_path in iter_repo_files(repo_root):
        suffix = rel_path.suffix.lower()
        if suffix and suffix not in SUPPORTED_SUFFIXES:
            continue
        posix = rel_path.as_posix()
        if _matches_extra(posix, extra_patterns):
            continue
        absolute = repo_root / rel_path
        if not absolute.is_file():
            continue
        try:
            stat = absolute.stat()
            cached = cached_meta.get(posix)
            
            # Fast path: if mtime and size match, reuse cached hash
            if cached is not None:
                cached_hash, cached_mtime, cached_size = cached
                # Use small epsilon for float comparison on mtime
                if abs(stat.st_mtime - cached_mtime) < 0.001 and stat.st_size == cached_size:
                    hashes[posix] = cached_hash
                    skipped_count += 1
                    continue
            
            # Slow path: compute hash for new/modified files
            hashes[posix] = sha256_file(absolute)
            hashed_count += 1
        except OSError:
            continue
    
    # Log stats when there's meaningful work (helps diagnose perf issues)
    if hashed_count > 0:
        log(f"Hashed {hashed_count} files, skipped {skipped_count} unchanged")

    return hashes


def detect_changes(repo_root: Path, index_path: Path | None = None) -> list[str]:
    """Detect files that changed since last index.
    
    Uses smart mtime/size filtering to avoid hashing unchanged files.
    O(N) stat calls but only O(changed) hash computations.
    """
    index_path = index_path or index_path_for_write(repo_root)
    extra = _extra_patterns(repo_root)
    
    # Load cached metadata for smart filtering
    cached_meta = load_cached_file_meta(index_path)
    
    # Use smart hashing: mtime/size filter before SHA256
    current = current_hashes_smart(repo_root, extra, cached_meta)
    
    if not cached_meta:
        # No prior index - everything is new
        return sorted(current.keys())
    
    # Build hash-only lookup for comparison
    cached_hashes = {path: meta[0] for path, meta in cached_meta.items()}
    
    dirty = {path for path, digest in current.items() if cached_hashes.get(path) != digest}
    deleted = {path for path in cached_hashes.keys() if path not in current}
    dirty.update(deleted)
    return sorted(dirty)


def _python_env() -> list[str]:
    return [sys.executable]


def run_sync(repo_root: Path, paths: Sequence[str]) -> None:
    if not paths:
        return
    cmd = _python_env() + ["-m", "llmc.rag.cli", "sync"]
    for path in paths:
        cmd.extend(["--path", path])
    log(f"Syncing {len(paths)} paths")
    env = os.environ.copy()
    # Ensure LLMC_PROD tooling is importable when cwd=repo_root
    py_paths = [str(PROJECT_ROOT)]
    if env.get("PYTHONPATH"):
        py_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(py_paths)
    subprocess.run(cmd, cwd=repo_root, check=True, env=env)


def run_embed(repo_root: Path, limit: int) -> str:
    cmd = _python_env() + [
        "-m",
        "llmc.rag.cli",
        "embed",
        "--execute",
        "--limit",
        str(limit),
    ]
    env = os.environ.copy()
    py_paths = [str(PROJECT_ROOT)]
    if env.get("PYTHONPATH"):
        py_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(py_paths)
    result = subprocess.run(
        cmd, check=False, cwd=repo_root, capture_output=True, text=True, env=env
    )

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if stdout:
        # Preserve the original embed CLI output in service logs.
        logger.info(stdout)
    if stderr:
        # Surface embedding errors that would otherwise be hidden when run via the daemon.
        logger.error(stderr)

    if result.returncode != 0:
        # Propagate a rich error object while keeping existing caller behavior.
        raise subprocess.CalledProcessError(
            result.returncode,
            cmd,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result.stdout


def run_stats(repo_root: Path) -> None:
    cmd = _python_env() + ["-m", "llmc.rag.cli", "stats"]
    env = os.environ.copy()
    py_paths = [str(PROJECT_ROOT)]
    if env.get("PYTHONPATH"):
        py_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(py_paths)
    subprocess.run(cmd, cwd=repo_root, check=True, env=env)


def run_enrich(
    repo_root: Path,
    backend: str,
    router: str,
    start_tier: str,
    batch_size: int,
    max_spans: int,
    cooldown: int,
) -> None:
    # Prefer target repo script; fallback to LLMC_PROD's script if missing
    script = repo_root / "scripts" / "qwen_enrich_batch.py"
    if not script.exists():
        script = PROJECT_ROOT / "scripts" / "qwen_enrich_batch.py"
    cmd = _python_env() + [
        str(script),
        "--repo",
        str(repo_root),
        "--backend",
        backend,
        "--batch-size",
        str(batch_size),
        "--router",
        router,
        "--start-tier",
        start_tier,
        "--max-spans",
        str(max_spans),
    ]
    if cooldown:
        cmd.extend(["--cooldown", str(cooldown)])

    env = os.environ.copy()
    env.update({"LLM_DISABLED": "false", "NEXT_PUBLIC_LLM_DISABLED": "false"})
    # Optional summary JSON for enrichment runs, used by unified CLI.
    try:
        summary_path = repo_root / ".llmc" / "enrich_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        env["LLMC_ENRICH_SUMMARY_JSON"] = str(summary_path)
    except Exception:
        # Best-effort only; failures here must not block enrichment.
        pass
    # Ensure both the target repo and LLMC_PROD tooling are importable
    py_paths = [str(repo_root), str(PROJECT_ROOT)]
    if env.get("PYTHONPATH"):
        py_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(py_paths)

    timeout_raw = env.get("ENRICH_SUBPROCESS_TIMEOUT_SECONDS", "3600")
    try:
        timeout_s = int(timeout_raw)
    except ValueError:
        timeout_s = 3600

    try:
        subprocess.run(
            cmd,
            cwd=repo_root,
            check=True,
            env=env,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"enrichment subprocess timed out after {timeout_s}s for repo {repo_root}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        if exc.returncode == 2:
            raise RuntimeError(
                "No reachable LLM hosts found. Is Athena (or configured backend) down?"
            ) from exc
        raise


def command_detect(args: argparse.Namespace) -> None:
    repo = (args.repo or find_repo_root()).resolve()
    index_path = args.index
    if index_path:
        index_path = Path(index_path).resolve()
    changes = detect_changes(repo, index_path)
    if args.json:
        print(json.dumps(changes))
    else:
        for path in changes:
            print(path)


def ensure_doc_sync(repo_root: Path, doc_paths: Sequence[str]) -> None:
    existing = [doc for doc in doc_paths if (repo_root / doc).exists()]
    if not existing:
        return
    cmd = _python_env() + ["-m", "llmc.rag.cli", "sync"]
    for doc in existing:
        cmd.extend(["--path", doc])
    log(f"Syncing documented paths: {', '.join(existing)}")
    subprocess.run(cmd, cwd=repo_root, check=True)


def command_indexenrich(args: argparse.Namespace) -> None:
    repo = (args.repo or find_repo_root()).resolve()
    doc_paths = args.doc_path or [
        "DOCS/preprocessor_flow.md",
        "DOCS/archive/preprocessor_flow_legacy.md",
    ]
    ensure_doc_sync(repo, doc_paths)

    index_path = index_path_for_write(repo)
    changes = detect_changes(repo, index_path=index_path)
    if changes:
        run_sync(repo, changes)
    else:
        log("No file diffs detected (workspace matches RAG cache).")

    backend = args.backend or (
        "gateway" if args.force_nano else os.getenv("ENRICH_BACKEND", "ollama")
    )
    router = args.router or os.getenv("ENRICH_ROUTER", "off")
    start_tier = args.start_tier or os.getenv(
        "ENRICH_START_TIER", ("nano" if args.force_nano else "7b")
    )
    run_enrich(
        repo,
        backend=backend,
        router=router,
        start_tier=start_tier,
        batch_size=args.batch_size,
        max_spans=0,
        cooldown=0,
    )

    embed_limit = args.embed_limit or env_int("RAG_REFRESH_EMBED_LIMIT", 256)
    max_iters = args.embed_iterations
    for _ in range(max_iters):
        output = run_embed(repo, embed_limit)
        if "No spans pending embedding." in output:
            break
        if "Stored embeddings for" not in output:
            break

    run_stats(repo)


def command_refresh(args: argparse.Namespace) -> None:
    repo = (args.repo or find_repo_root()).resolve()
    index_path = index_path_for_write(repo)
    changes = detect_changes(repo, index_path=index_path)
    force = args.force or env_bool("RAG_REFRESH_FORCE", False)
    if not changes and not force:
        log("No tracked changes detected; skipping refresh.")
        return
    if changes:
        run_sync(repo, changes)
    else:
        log("No diffs detected but forcing refresh via RAG_REFRESH_FORCE/--force")

    skip_enrich = args.skip_enrich or env_bool("RAG_REFRESH_SKIP_ENRICH", False)
    skip_embed = args.skip_embed or env_bool("RAG_REFRESH_SKIP_EMBED", False)
    skip_stats = args.skip_stats or env_bool("RAG_REFRESH_SKIP_STATS", False)

    if not skip_enrich:
        backend = os.getenv("RAG_REFRESH_BACKEND", "ollama")
        router = os.getenv("RAG_REFRESH_ROUTER", "off")
        start_tier = os.getenv("RAG_REFRESH_START_TIER", "7b")
        batch_size = env_int("RAG_REFRESH_BATCH_SIZE", 5)
        max_spans = env_int("RAG_REFRESH_MAX_SPANS", 0)
        cooldown = env_int("RAG_REFRESH_COOLDOWN", 300)
        run_enrich(repo, backend, router, start_tier, batch_size, max_spans, cooldown)
    else:
        log("Skipping enrichment per flag")

    if not skip_embed:
        limit = env_int("RAG_REFRESH_EMBED_LIMIT", 100)
        run_embed(repo, limit)
    else:
        log("Skipping embedding refresh per flag")

    if not skip_stats:
        run_stats(repo)
    else:
        log("Skipping stats per flag")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified RAG maintenance runner")
    sub = parser.add_subparsers(dest="command", required=True)

    detect_parser = sub.add_parser(
        "detect", help="List files whose hashes differ from the RAG index"
    )
    detect_parser.add_argument("--repo", type=Path, default=None)
    detect_parser.add_argument("--index", type=Path, default=None)
    detect_parser.add_argument("--json", action="store_true")
    detect_parser.set_defaults(func=command_detect)

    idx_parser = sub.add_parser(
        "indexenrich", help="Incremental sync + enrich + embed pipeline"
    )
    idx_parser.add_argument("--repo", type=Path, default=None)
    idx_parser.add_argument(
        "--doc-path", action="append", help="Additional doc paths to always sync"
    )
    idx_parser.add_argument("--backend", default=None)
    idx_parser.add_argument("--router", default=None)
    idx_parser.add_argument("--start-tier", default=None)
    idx_parser.add_argument("--batch-size", type=int, default=5)
    idx_parser.add_argument("--embed-limit", type=int, default=None)
    idx_parser.add_argument("--embed-iterations", type=int, default=20)
    idx_parser.add_argument(
        "--force-nano", action="store_true", help="Force nano tier via gateway backend"
    )
    idx_parser.set_defaults(func=command_indexenrich)

    refresh_parser = sub.add_parser("refresh", help="General-purpose RAG refresh loop")
    refresh_parser.add_argument("--repo", type=Path, default=None)
    refresh_parser.add_argument("--force", action="store_true")
    refresh_parser.add_argument("--skip-enrich", action="store_true")
    refresh_parser.add_argument("--skip-embed", action="store_true")
    refresh_parser.add_argument("--skip-stats", action="store_true")
    refresh_parser.set_defaults(func=command_refresh)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
