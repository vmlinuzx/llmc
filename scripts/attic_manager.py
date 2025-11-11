#!/usr/bin/env python3
"""
Attic Manager - Step 3: Repo Cleanup
Manages quarantine/moved files with manifests
"""

import json
import shutil
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

class AtticManager:
    """Manages files moved to the attic with manifests."""

    def __init__(self, repo_root: Path, attic_root: Path):
        self.repo_root = repo_root
        self.attic_root = attic_root
        self.manifest_path = attic_root / "manifest.json"

    def move_to_attic(self, file_path: Path, reason: str, planned_purge_version: str = "TBD") -> bool:
        """Move file to attic with manifest."""
        try:
            if not file_path.exists():
                print(f"❌ File not found: {file_path}")
                return False

            # Create attic subdirectory by reason
            reason_dir = self.attic_root / reason.replace(" ", "_")
            reason_dir.mkdir(exist_ok=True)

            # Generate target path
            target_path = reason_dir / file_path.name
            if target_path.exists():
                # Add timestamp to avoid conflicts
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                stem = target_path.stem
                suffix = target_path.suffix
                target_path = reason_dir / f"{stem}_{timestamp}{suffix}"

            # Create manifest entry
            manifest_entry = {
                "original_path": str(file_path.relative_to(self.repo_root)),
                "attic_path": str(target_path.relative_to(self.attic_root)),
                "moved_at": datetime.now().isoformat(),
                "reason": reason,
                "planned_purge_version": planned_purge_version,
                "keep": False
            }

            # Move file
            shutil.move(str(file_path), str(target_path))
            print(f"📦 Moved: {file_path} → {target_path}")

            # Update manifest
            self._update_manifest(manifest_entry)

            return True

        except Exception as e:
            print(f"❌ Error moving {file_path}: {e}")
            return False

    def _update_manifest(self, entry: Dict[str, Any]):
        """Update the attic manifest with new entry."""
        manifest = self._load_manifest()

        # Check if entry already exists
        for i, existing_entry in enumerate(manifest):
            if existing_entry["original_path"] == entry["original_path"]:
                manifest[i] = entry
                break
        else:
            manifest.append(entry)

        # Save manifest
        with open(self.manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

    def _load_manifest(self) -> list:
        """Load the attic manifest."""
        if not self.manifest_path.exists():
            return []

        try:
            with open(self.manifest_path, 'r') as f:
                return json.load(f)
        except:
            return []

    def check_references(self) -> list:
        """Check if working tree references quarantined files."""
        violations = []

        manifest = self._load_manifest()
        attic_files = {entry["original_path"] for entry in manifest}

        # Scan scripts for references to attic files
        for script_path in self.repo_root.rglob("*.sh"):
            try:
                with open(script_path, 'r') as f:
                    content = f.read()

                for attic_file in attic_files:
                    if attic_file in content:
                        violations.append({
                            "script": str(script_path.relative_to(self.repo_root)),
                            "references": attic_file
                        })

            except:
                pass

        return violations

    def generate_report(self) -> Dict[str, Any]:
        """Generate cleanup report."""
        manifest = self._load_manifest()

        by_reason = {}
        total_size = 0

        for entry in manifest:
            reason = entry["reason"]
            if reason not in by_reason:
                by_reason[reason] = []
            by_reason[reason].append(entry)
            total_size += entry.get("size", 0)

        return {
            "total_moved_files": len(manifest),
            "by_reason": {k: len(v) for k, v in by_reason.items()},
            "total_size_bytes": total_size,
            "manifest_entries": manifest
        }

def main():
    """Main entry point."""
    repo_root = Path(__file__).parent.parent
    attic_root = repo_root / ".trash"

    manager = AtticManager(repo_root, attic_root)

    print("🏠 Attic Manager - Step 3")
    print("=" * 30)

    # Check for references to quarantined files
    print("🔍 Checking for references to quarantined files...")
    violations = manager.check_references()

    if violations:
        print("⚠️  Found references to quarantined files:")
        for violation in violations:
            print(f"  {violation['script']} → {violation['references']}")
    else:
        print("✅ No references to quarantined files found")

    # Generate report
    print("\n📊 Attic Report:")
    report = manager.generate_report()
    print(f"  Total moved files: {report['total_moved_files']}")
    print(f"  By reason: {report['by_reason']}")

if __name__ == "__main__":
    main()