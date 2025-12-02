#!/usr/bin/env python3
"""
LLMC Log Manager - Simple, lightweight log rotation module.

Usage:
    python llmc_log_manager.py --help
    python llmc_log_manager.py --check /path/to/logs
    python llmc_log_manager.py --rotate --max-size 10MB /path/to/logs

Now supports optional TOML configuration via `llmc.toml` with section [logging]:
  - max_file_size_mb (int)
  - keep_jsonl_lines (int)
  - enable_rotation (bool)
  - log_directory (str)
"""

import argparse
from pathlib import Path
import time
from typing import Any

try:  # Python 3.11+
    import tomllib  # type: ignore
except Exception:  # pragma: no cover - older Python
    tomllib = None  # type: ignore


def load_logging_config(config_path: Path) -> dict[str, Any]:
    """Load [logging] config from a TOML file if present.

    Returns an empty dict if file not found or tomllib unavailable.
    """
    if not config_path.exists() or tomllib is None:
        return {}
    try:
        with config_path.open("rb") as fh:
            data = tomllib.load(fh) or {}
        section = data.get("logging") or {}
        return section if isinstance(section, dict) else {}
    except Exception:
        # Fail closed to avoid breaking rotation due to config parse issues
        return {}


class LLMCLogManager:
    """Simple log rotation with summary output.

    Parameters:
        max_size_mb: Max size for non-JSONL logs before truncation.
        keep_jsonl_lines: Number of tail lines to keep for JSONL files.
        enabled: Master switch to enable/disable rotation.
    """

    def __init__(self, max_size_mb: int = 10, keep_jsonl_lines: int = 1000, enabled: bool = True):
        self.max_size_bytes = int(max_size_mb) * 1024 * 1024
        self.keep_jsonl_lines = int(keep_jsonl_lines)
        self.enabled = bool(enabled)
    
    def find_log_files(self, log_dir: Path) -> list[Path]:
        """Find all log files in directory."""
        if not log_dir.exists():
            return []
        
        patterns = ["*.log", "*.log.*", "*.jsonl"]
        files: list[Path] = []
        for pattern in patterns:
            files.extend(log_dir.glob(pattern))
        return sorted(files)
    
    def get_file_size_info(self, file_path: Path) -> dict[str, Any]:
        """Get file size and modification info."""
        if not file_path.exists():
            return {"exists": False}
        
        stat = file_path.stat()
        return {
            "exists": True,
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": time.ctime(stat.st_mtime),
            "age_hours": round((time.time() - stat.st_mtime) / 3600, 1)
        }
    
    def truncate_log(self, file_path: Path, keep_lines: int | None = None) -> dict[str, Any]:
        """Truncate log file to last N lines (JSONL) or by size (others)."""
        if not file_path.exists():
            return {"error": "File doesn't exist"}

        original_size = file_path.stat().st_size

        # For JSONL files, keep structure intact
        if file_path.suffix == '.jsonl':
            # Determine number of lines to keep
            n_keep = self.keep_jsonl_lines if keep_lines is None else int(keep_lines)
            lines = file_path.read_text().splitlines()
            if len(lines) <= n_keep:
                return {"truncated": False, "reason": "File already small enough"}

            truncated_lines = lines[-n_keep:]
            file_path.write_text("\n".join(truncated_lines))
            new_size = file_path.stat().st_size
            bytes_saved = original_size - new_size

            return {
                "truncated": True,
                "bytes_saved": bytes_saved,
                "lines_kept": n_keep,
                "lines_removed": len(lines) - n_keep
            }
        
        # For regular logs, just truncate to max size
        if original_size > self.max_size_bytes:
            # Simple truncate - keep last portion of file
            content = file_path.read_text()
            if len(content) > self.max_size_bytes:
                # Keep last max_size_bytes characters
                truncated = content[-self.max_size_bytes:]
                file_path.write_text(truncated)
                return {
                    "truncated": True,
                    "bytes_saved": original_size - len(truncated.encode()),
                    "method": "size_truncate"
                }
        
        return {"truncated": False, "reason": "File within size limit"}
    
    def check_logs(self, log_dir: Path) -> dict[str, Any]:
        """Check all logs and return summary."""
        log_files = self.find_log_files(log_dir)
        results = []
        total_size = 0
        oversized_files = []
        
        for log_file in log_files:
            info = self.get_file_size_info(log_file)
            results.append({
                "file": str(log_file.relative_to(log_dir)),
                **info
            })
            
            if info.get("exists", False):
                total_size += info["size_bytes"]
                if info["size_bytes"] > self.max_size_bytes:
                    oversized_files.append(log_file)
        
        return {
            "log_directory": str(log_dir),
            "total_files": len(log_files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oversized_count": len(oversized_files),
            "files": results
        }
    
    def rotate_logs(self, log_dir: Path) -> dict[str, Any]:
        """Rotate logs that exceed size limit.

        Respects the manager's `enabled` flag; returns a no-op summary if disabled.
        """
        if not self.enabled:
            return {"rotated_files": 0, "rotations": [], "max_size_mb": self.max_size_bytes // (1024 * 1024)}
        oversized = []
        rotation_summary = []
        
        for log_file in self.find_log_files(log_dir):
            info = self.get_file_size_info(log_file)
            
            if info.get("exists", False) and info["size_bytes"] > self.max_size_bytes:
                truncate_result = self.truncate_log(log_file)
                rotate_info = {
                    "file": str(log_file.relative_to(log_dir)),
                    "original_size_mb": info["size_mb"],
                    "action": "truncated"
                }
                
                if truncate_result.get("truncated"):
                    rotate_info.update(truncate_result)
                    oversized.append(rotate_info)
                
                rotation_summary.append(rotate_info)
        
        return {
            "rotated_files": len(oversized),
            "rotations": rotation_summary,
            "max_size_mb": self.max_size_bytes // (1024 * 1024),
        }


def main():
    parser = argparse.ArgumentParser(
        description="LLMC Log Manager - Simple log rotation",
        epilog="Examples:\n"
               "  llmc_log_manager.py --check logs/\n"
               "  llmc_log_manager.py --rotate logs/\n"
               "  llmc_log_manager.py --rotate --max-size 5 logs/"
    )
    parser.add_argument("log_dir", nargs="?", help="Log directory path (overrides config)")
    parser.add_argument("--check", action="store_true", help="Check log sizes without rotating")
    parser.add_argument("--rotate", action="store_true", help="Rotate oversized logs")
    parser.add_argument("--max-size", default="10MB", help="Max log file size (default: 10MB)")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    parser.add_argument("--config", help="Path to llmc.toml (optional)")

    args = parser.parse_args()

    # Determine repo root for resolving config and relative log directories
    repo_root = Path(__file__).resolve().parents[1]

    # Load optional logging config
    cfg_path = Path(args.config) if args.config else (repo_root / "llmc.toml")
    cfg = load_logging_config(cfg_path)

    # Parse size: CLI overrides config
    if args.max_size.endswith("MB"):
        max_mb = int(args.max_size[:-2])
    elif args.max_size.endswith("KB"):
        max_mb = int(args.max_size[:-2]) / 1024
    else:
        max_mb = int(args.max_size)
    max_mb = int(cfg.get("max_file_size_mb", max_mb))

    keep_lines = int(cfg.get("keep_jsonl_lines", 1000))
    enabled = bool(cfg.get("enable_rotation", True))

    manager = LLMCLogManager(max_mb, keep_lines, enabled)

    # Resolve log directory: positional overrides config key
    cfg_log_dir = cfg.get("log_directory")
    if args.log_dir:
        log_dir = Path(args.log_dir)
    elif cfg_log_dir:
        log_dir = Path(str(cfg_log_dir))
        if not log_dir.is_absolute():
            log_dir = (repo_root / log_dir).resolve()
    else:
        if args.check or args.rotate:
            parser.error("Log directory required (positional or [logging].log_directory)")
        else:
            parser.print_help()
            return

    if args.check:
        result = manager.check_logs(log_dir)
        if not args.quiet:
            print("📊 Log Check Summary")
            print(f"   Directory: {result['log_directory']}")
            print(f"   Total files: {result['total_files']}")
            print(f"   Total size: {result['total_size_mb']} MB")
            print(f"   Oversized: {result['oversized_count']}")
            
            if result['oversized_count'] > 0:
                print("\n⚠️  Oversized files:")
                for file_info in result['files']:
                    if file_info.get('size_bytes', 0) > manager.max_size_bytes:
                        print(f"   {file_info['file']}: {file_info['size_mb']} MB")
            else:
                print("✅ All logs within size limit")
    elif args.rotate:
        result = manager.rotate_logs(log_dir)
        if not args.quiet:
            if result['rotated_files'] > 0:
                print("🔄 Log Rotation Complete")
                print(f"   Rotated: {result['rotated_files']} files")
                for rotation in result['rotations']:
                    if rotation.get('truncated'):
                        if 'bytes_saved' in rotation:
                            print(f"   {rotation['file']}: saved {round(rotation['bytes_saved']/1024/1024, 1)} MB")
            else:
                print("✅ No logs needed rotation")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
