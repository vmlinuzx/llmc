#!/usr/bin/env python3
"""
Sync LLMC repo to Google Drive, honoring .gitignore.

Just run it. It works. No arguments, no bullshit.

Syncs tracked + untracked-but-not-ignored files to:
  dcgoogledrive:llmc/

Requirements:
- Python 3.8+
- rclone configured with 'dcgoogledrive' remote
- Git repo with .gitignore
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

RCLONE_REMOTE = "dcgoogledrive:"
REMOTE_DIR = "llmc"


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> tuple[int, str, str]:
    """Run command and return (returncode, stdout, stderr)."""
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate()
    if check and proc.returncode != 0:
        print(f"Error: {' '.join(cmd)}", file=sys.stderr)
        if err:
            print(err, file=sys.stderr)
        sys.exit(proc.returncode)
    return proc.returncode, out, err


def find_repo_root() -> Path:
    """Find git repo root."""
    rc, out, _ = run(["git", "rev-parse", "--show-toplevel"], check=False)
    if rc == 0 and out.strip():
        return Path(out.strip())
    
    # Fallback: look for .git directory
    cur = Path.cwd().resolve()
    for parent in [cur] + list(cur.parents):
        if (parent / ".git").exists():
            return parent
    
    print("Error: Not in a git repository", file=sys.stderr)
    sys.exit(1)


def get_git_files(repo_root: Path) -> list[str]:
    """Get list of files respecting .gitignore (tracked + untracked but not ignored)."""
    rc, out, err = run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=repo_root,
        check=True
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def create_filter_file(repo_root: Path, files: list[str]) -> Path:
    """Create rclone filter file from git file list."""
    filter_path = repo_root / ".rclone-filter"
    
    with open(filter_path, "w") as f:
        # Include only the files git knows about
        for file in files:
            f.write(f"+ /{file}\n")
        
        # Exclude everything else
        f.write("- *\n")
    
    return filter_path


def generate_chart(repo_root: Path, files: list[str], chart_path: Path) -> None:
    """Generate a tree-style repository chart using 'tree'."""
    print(f"Generating repository chart: {chart_path.name}")
    
    # Prepare input for tree --fromfile
    # tree expects paths relative to CWD
    input_str = "\n".join(files)
    
    # Run tree command
    # We pipe the file list to stdin
    proc = subprocess.Popen(
        ["tree", "--fromfile", "."],
        cwd=repo_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, err = proc.communicate(input=input_str)
    
    if proc.returncode != 0:
        print(f"Warning: Failed to generate chart with 'tree': {err}", file=sys.stderr)
        # Fallback: simple list
        with open(chart_path, "w") as f:
            f.write("Repository File List:\n\n")
            f.write(input_str)
    else:
        with open(chart_path, "w") as f:
            f.write(out)


def sync_to_gdrive(repo_root: Path, filter_file: Path) -> None:
    """Sync repo to Google Drive using rclone."""
    remote_path = f"{RCLONE_REMOTE}{REMOTE_DIR}"
    
    print(f"Syncing {repo_root.name} to {remote_path}/")
    print("This syncs tracked + untracked files (honoring .gitignore)")
    print("")
    
    # Run rclone sync with filter
    run([
        "rclone", "sync",
        str(repo_root),
        remote_path,
        "--filter-from", str(filter_file),
        "--progress",
        "--stats", "5s",
    ])
    
    print("")
    print(f"✓ Synced to Google Drive: {remote_path}/")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="""
Sync LLMC repo to Google Drive (LIVE MIRROR).

Use this script to keep a 1:1 copy of your active codebase in the 'llmc/' folder on Google Drive.
It respects .gitignore, so it only syncs what you care about.

Use 'upload_context_to_gdrive.py' if you want zipped snapshots/backups instead.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.parse_args()

    # Find repo
    repo_root = find_repo_root()
    print(f"Repository: {repo_root}")
    
    # Get files respecting .gitignore
    print("Getting file list (respecting .gitignore)...")
    files = get_git_files(repo_root)
    print(f"Found {len(files)} files to sync")
    
    if not files:
        print("No files to sync!", file=sys.stderr)
        return 1
    
    # Generate repository chart
    chart_path = repo_root / "repository_chart.txt"
    generate_chart(repo_root, files, chart_path)
    
    # Add chart to files list so it gets included in filter
    files.append(chart_path.name)

    # Create filter file
    filter_file = create_filter_file(repo_root, files)
    
    try:
        # Sync to Google Drive
        sync_to_gdrive(repo_root, filter_file)
    finally:
        # Clean up
        if filter_file.exists():
            filter_file.unlink()
        if chart_path.exists():
            chart_path.unlink()
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
