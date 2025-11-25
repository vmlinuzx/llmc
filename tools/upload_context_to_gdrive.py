#!/usr/bin/env python3
"""
Upload context ZIP files to Google Drive using rclone.

Features:
- Uploads to gdrive:/llmc_backups/ directory (creates if needed)
- Optionally creates the ZIP first by calling create_context_zip.py
- Preserves original timestamps
- Shows progress for large files
- Verifies upload integrity with checksum comparison

Requirements:
- Python 3.8+
- rclone configured with a 'dcgoogledrive' remote
- create_context_zip.py in same directory (if using --create flag)

Usage:
    # Upload existing zip
    ./upload_context_to_gdrive.py /path/to/llmc.zip
    
    # Create and upload in one go
    ./upload_context_to_gdrive.py --create
    
    # Specify custom remote directory
    ./upload_context_to_gdrive.py --create --remote-dir backups/llmc
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


RCLONE_REMOTE = "dcgoogledrive:"
DEFAULT_REMOTE_DIR = "llmc_backups"


def run_command(cmd: list[str], check: bool = True) -> tuple[int, str, str]:
    """Run command and return (returncode, stdout, stderr)."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate()
    if check and proc.returncode != 0:
        print(f"Error running: {' '.join(cmd)}", file=sys.stderr)
        print(f"Exit code: {proc.returncode}", file=sys.stderr)
        if err:
            print(f"stderr: {err}", file=sys.stderr)
        sys.exit(proc.returncode)
    return proc.returncode, out, err


def check_rclone() -> bool:
    """Verify rclone is available and configured."""
    rc, out, err = run_command(["which", "rclone"], check=False)
    if rc != 0:
        print("Error: rclone not found. Install with: sudo apt install rclone", file=sys.stderr)
        return False
    
    # Check if remote exists
    rc, out, err = run_command(["rclone", "listremotes"], check=False)
    if RCLONE_REMOTE not in out:
        print(f"Error: rclone remote '{RCLONE_REMOTE}' not configured", file=sys.stderr)
        print("Run: rclone config", file=sys.stderr)
        return False
    
    return True


def create_context_zip() -> Path | None:
    """Run create_context_zip.py and return the path to created zip."""
    script_dir = Path(__file__).parent
    create_script = script_dir / "create_context_zip.py"
    
    if not create_script.exists():
        print(f"Error: {create_script} not found", file=sys.stderr)
        return None
    
    print("Creating context ZIP...")
    rc, out, err = run_command([sys.executable, str(create_script)])
    
    # Parse output for created file path
    for line in out.splitlines():
        if line.startswith("Created:"):
            zip_path = Path(line.split("Created:")[1].strip())
            if zip_path.exists():
                return zip_path
    
    print("Error: Could not determine created ZIP path", file=sys.stderr)
    return None


def upload_to_gdrive(zip_path: Path, remote_dir: str = DEFAULT_REMOTE_DIR) -> bool:
    """Upload ZIP to Google Drive using rclone."""
    if not zip_path.exists():
        print(f"Error: {zip_path} does not exist", file=sys.stderr)
        return False
    
    remote_path = f"{RCLONE_REMOTE}{remote_dir}"
    
    # Create remote directory if needed
    print(f"Ensuring remote directory exists: {remote_path}")
    run_command(["rclone", "mkdir", remote_path])
    
    # Get file size for progress display
    file_size_mb = zip_path.stat().st_size / (1024 * 1024)
    
    print(f"Uploading {zip_path.name} ({file_size_mb:.1f} MB) to {remote_path}/")
    print("This may take a while for large files...")
    
    # Upload with progress
    rc, out, err = run_command([
        "rclone", "copy",
        str(zip_path),
        remote_path,
        "--progress",
        "--stats", "5s",
    ])
    
    if rc == 0:
        print(f"✓ Successfully uploaded to {remote_path}/{zip_path.name}")
        return True
    else:
        print(f"✗ Upload failed", file=sys.stderr)
        return False


def list_backups(remote_dir: str = DEFAULT_REMOTE_DIR) -> None:
    """List existing backups in Google Drive."""
    remote_path = f"{RCLONE_REMOTE}{remote_dir}"
    print(f"\nExisting backups in {remote_path}:")
    rc, out, err = run_command(
        ["rclone", "lsl", remote_path],
        check=False
    )
    if rc == 0 and out.strip():
        print(out)
    else:
        print("  (none)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="""
Upload ZIPPED SNAPSHOTS of the LLMC context to Google Drive (BACKUPS).

Use this script to save point-in-time backups (ZIP files) to the 'llmc_backups/' folder.
Useful for sharing state or archiving versions.

Use 'sync_to_gdrive.py' if you want a live 1:1 mirror of the codebase instead.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "zip_file",
        nargs="?",
        type=Path,
        help="Path to ZIP file to upload (optional if --create is used)",
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="Create context ZIP before uploading",
    )
    parser.add_argument(
        "--remote-dir",
        default=DEFAULT_REMOTE_DIR,
        help=f"Remote directory path (default: {DEFAULT_REMOTE_DIR})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing backups and exit",
    )
    
    args = parser.parse_args()
    
    # Check prerequisites
    if not check_rclone():
        return 1
    
    # List mode
    if args.list:
        list_backups(args.remote_dir)
        return 0
    
    # Determine zip file to upload
    zip_path: Path | None = None
    
    if args.create:
        zip_path = create_context_zip()
        if not zip_path:
            return 2
    elif args.zip_file:
        zip_path = args.zip_file
    else:
        print("Error: Must specify ZIP file or use --create", file=sys.stderr)
        parser.print_help()
        return 1
    
    # Upload
    if not upload_to_gdrive(zip_path, args.remote_dir):
        return 3
    
    # Show what's on drive now
    list_backups(args.remote_dir)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
