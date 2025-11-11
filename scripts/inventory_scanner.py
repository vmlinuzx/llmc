#!/usr/bin/env python3
"""
Repository Inventory Scanner - Step 3: Repo Cleanup
Creates machine-readable inventory for classification: KEEP/MIGRATE/DELETE/QUARANTINE/ARCHIVE
"""

import json
import os
import re
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

class RepoInventoryScanner:
    """Scan repository and create machine-readable inventory."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.inventory = {
            "scan_date": datetime.now().isoformat(),
            "repo_root": str(repo_root),
            "files": [],
            "duplicates": [],
            "rag_usage": [],
            "suppression_usage": [],
            "wrappers": [],
            "statistics": {}
        }

    def scan_repository(self):
        """Main scanning function."""
        print("🔍 Scanning repository for inventory...")

        # Scan all files
        self._scan_files()

        # Find duplicates
        self._find_duplicates()

        # Analyze RAG usage
        self._analyze_rag_usage()

        # Analyze suppression usage
        self._analyze_suppression_usage()

        # Analyze wrapper scripts
        self._analyze_wrappers()

        # Generate statistics
        self._generate_statistics()

        return self.inventory

    def _scan_files(self):
        """Scan all files in repository."""
        print("📁 Scanning files...")

        for file_path in self.repo_root.rglob("*"):
            if file_path.is_file() and self._should_include_file(file_path):
                file_info = self._analyze_file(file_path)
                if file_info:
                    self.inventory["files"].append(file_info)

    def _should_include_file(self, file_path: Path) -> bool:
        """Determine if file should be included in inventory."""
        # Skip common ignore patterns
        skip_patterns = [
            ".git", "__pycache__", ".pyc", ".DS_Store",
            "node_modules", ".venv", "venv", "logs/autosave.log"
        ]

        for pattern in skip_patterns:
            if pattern in str(file_path):
                return False

        return True

    def _analyze_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Analyze a single file."""
        try:
            stat = file_path.stat()
            relative_path = str(file_path.relative_to(self.repo_root))

            file_info = {
                "path": relative_path,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "type": self._get_file_type(file_path),
                "is_executable": os.access(file_path, os.X_OK),
                "tags": []
            }

            # Add tags based on path and content
            self._add_tags(file_path, file_info)

            return file_info

        except Exception as e:
            print(f"⚠️  Error analyzing {file_path}: {e}")
            return None

    def _get_file_type(self, file_path: Path) -> str:
        """Determine file type."""
        suffix = file_path.suffix.lower()

        type_map = {
            ".py": "python",
            ".sh": "shell",
            ".js": "javascript",
            ".ts": "typescript",
            ".md": "markdown",
            ".json": "json",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".txt": "text",
            ".sql": "sql"
        }

        return type_map.get(suffix, "other")

    def _add_tags(self, file_path: Path, file_info: Dict[str, Any]):
        """Add relevant tags to file info."""
        path_str = str(file_path)

        # Wrapper detection
        if "wrap" in path_str.lower():
            file_info["tags"].append("wrapper")

        # RAG-related detection
        if "rag" in path_str.lower():
            file_info["tags"].append("rag-related")

        # CLI detection
        if "cli" in path_str.lower() or "llmc" in path_str.lower():
            file_info["tags"].append("cli")

        # Gateway detection
        if "gateway" in path_str.lower():
            file_info["tags"].append("gateway")

        # Test detection
        if "test" in path_str.lower():
            file_info["tags"].append("test")

        # Configuration detection
        if any(x in path_str.lower() for x in [".env", "config", "setup"]):
            file_info["tags"].append("config")

        # Scripts directory
        if "/scripts/" in path_str:
            file_info["tags"].append("script")

        # Check for RAG content
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if "rag_plan" in content.lower():
                    file_info["tags"].append("contains-rag-logic")
                if "2>/dev/null" in content:
                    file_info["tags"].append("contains-suppression")
        except:
            pass

    def _find_duplicates(self):
        """Find duplicate files by name and content."""
        print("🔍 Finding duplicates...")

        # Group by filename
        filename_groups = {}
        for file_info in self.inventory["files"]:
            filename = os.path.basename(file_info["path"])
            if filename not in filename_groups:
                filename_groups[filename] = []
            filename_groups[filename].append(file_info)

        # Find files with same name but different paths
        for filename, files in filename_groups.items():
            if len(files) > 1:
                duplicate_group = {
                    "filename": filename,
                    "files": [f["path"] for f in files],
                    "type": "same-name"
                }
                self.inventory["duplicates"].append(duplicate_group)

    def _analyze_rag_usage(self):
        """Analyze RAG usage patterns."""
        print("🔍 Analyzing RAG usage...")

        rag_patterns = [
            r"rag_plan",
            r"RAG_ENABLED",
            r"attachRagPlan",
            r"ragPlanSnippet"
        ]

        for file_info in self.inventory["files"]:
            if file_info["type"] in ["python", "shell", "javascript"]:
                file_path = self.repo_root / file_info["path"]
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    for pattern in rag_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            self.inventory["rag_usage"].append({
                                "file": file_info["path"],
                                "pattern": pattern,
                                "type": "pattern_match"
                            })
                            break

                except Exception:
                    pass

    def _analyze_suppression_usage(self):
        """Analyze suppression usage (2>/dev/null)."""
        print("🔍 Analyzing suppression usage...")

        for file_info in self.inventory["files"]:
            if file_info["type"] in ["shell", "python"]:
                file_path = self.repo_root / file_info["path"]
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    if "2>/dev/null" in content:
                        # Count occurrences
                        count = content.count("2>/dev/null")
                        self.inventory["suppression_usage"].append({
                            "file": file_info["path"],
                            "count": count,
                            "type": "suppression"
                        })

                except Exception:
                    pass

    def _analyze_wrappers(self):
        """Analyze wrapper script patterns."""
        print("🔍 Analyzing wrapper scripts...")

        wrapper_patterns = [
            r"#!/usr/bin/env bash",
            r"set -euo pipefail",
            r"EXEC_ROOT.*=",
            r"REPO_ROOT.*=",
            r"llm_gateway"
        ]

        for file_info in self.inventory["files"]:
            if file_info["type"] == "shell":
                file_path = self.repo_root / file_info["path"]
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    matches = sum(1 for pattern in wrapper_patterns if re.search(pattern, content))

                    if matches >= 3:  # Likely a wrapper
                        self.inventory["wrappers"].append({
                            "file": file_info["path"],
                            "match_score": matches,
                            "type": "wrapper_script"
                        })

                except Exception:
                    pass

    def _generate_statistics(self):
        """Generate inventory statistics."""
        files = self.inventory["files"]

        self.inventory["statistics"] = {
            "total_files": len(files),
            "by_type": {},
            "by_tag": {},
            "rag_files": len(self.inventory["rag_usage"]),
            "suppression_files": len(self.inventory["suppression_usage"]),
            "wrapper_files": len(self.inventory["wrappers"]),
            "duplicate_groups": len(self.inventory["duplicates"])
        }

        # Count by type
        for file_info in files:
            file_type = file_info["type"]
            self.inventory["statistics"]["by_type"][file_type] = \
                self.inventory["statistics"]["by_type"].get(file_type, 0) + 1

        # Count by tag
        for file_info in files:
            for tag in file_info["tags"]:
                self.inventory["statistics"]["by_tag"][tag] = \
                    self.inventory["statistics"]["by_tag"].get(tag, 0) + 1

    def save_inventory(self, output_path: Path):
        """Save inventory to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(self.inventory, f, indent=2)
        print(f"💾 Inventory saved to: {output_path}")

def main():
    """Main entry point."""
    repo_root = Path(__file__).parent.parent
    scanner = RepoInventoryScanner(repo_root)

    print("🚀 Repository Inventory Scanner - Step 3")
    print("=" * 50)

    inventory = scanner.scan_repository()

    # Save to various locations
    output_paths = [
        repo_root / "inventory.json",
        repo_root / ".repo-inventory.json"
    ]

    for output_path in output_paths:
        scanner.save_inventory(output_path)

    # Print summary
    stats = inventory["statistics"]
    print("\n📊 Inventory Summary:")
    print(f"  Total files: {stats['total_files']}")
    print(f"  RAG files: {stats['rag_files']}")
    print(f"  Suppression files: {stats['suppression_files']}")
    print(f"  Wrapper files: {stats['wrapper_files']}")
    print(f"  Duplicate groups: {stats['duplicate_groups']}")

    print("\n🏷️  Top file types:")
    for file_type, count in sorted(stats["by_type"].items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {file_type}: {count}")

    print("\n🏷️  Top tags:")
    for tag, count in sorted(stats["by_tag"].items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {tag}: {count}")

if __name__ == "__main__":
    main()