#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path

# Configuration
DOCS_ROOT = Path("DOCS")
IN_SCOPE_DIRS = [
    DOCS_ROOT / "getting-started",
    DOCS_ROOT / "user-guide",
    DOCS_ROOT / "operations",
    DOCS_ROOT / "architecture",
    DOCS_ROOT / "reference",
    DOCS_ROOT / "development",
]

LEGACY_TERMS = {
    "tools.rag": "llmc.rag",
    "llmc ask": "llmc chat",
    "llmc-rag-cli": "llmc-cli", # Often replaced or deprecated
    "llmc-rag-daemon": "llmc-cli daemon", # Verify this mapping
    "llmc-rag-repo": "llmc-cli repo", # Verify this mapping
}

# Diátaxis mapping (simplified)
DIATAXIS_MAP = {
    "getting-started": "Tutorial/Learning",
    "user-guide": "How-To",
    "operations": "How-To/Reference", # Can be mixed
    "architecture": "Explanation",
    "reference": "Reference",
    "development": "How-To/Explanation",
}

def get_files_in_scope():
    files = []
    for d in IN_SCOPE_DIRS:
        if d.exists():
            files.extend(list(d.rglob("*.md")))
    return files

def validate_links(file_path, content, all_files):
    issues = []
    # Match markdown links: [text](link)
    # This regex captures the link part
    links = re.findall(r'\[.*?\]\((.*?)\)', content)

    for link in links:
        # Ignore external links
        if link.startswith("http") or link.startswith("mailto:"):
            continue

        # Handle anchor only
        if link.startswith("#"):
            # TODO: Validate anchor in current file
            continue

        # Split anchor if present
        link_path_str = link.split("#")[0]
        anchor = link.split("#")[1] if "#" in link else None

        if not link_path_str:
            continue

        # Resolve path
        # If it starts with /, it's usually relative to repo root or doc root.
        # But markdown links are relative to the file usually.

        target_path = (file_path.parent / link_path_str).resolve()

        # Check if file exists
        if not target_path.exists():
            # Check if it might be relative to DOCS root or something else
            # But standard markdown is relative to file.
            issues.append(f"Broken link: {link} (resolved to {target_path})")
        else:
            if target_path.suffix == '.md' and anchor:
                # Check for anchor in target file
                try:
                    target_content = target_path.read_text()
                    # Simple header check: # Header or <a id="anchor">
                    # Normalize header to anchor format (lowercase, replace spaces with -)
                    # This is rough, as different renderers do different things.
                    # We'll just look for the text for now or exact match if explicitly defined.
                    pass
                except Exception as e:
                    pass

    return issues

def validate_legacy_terms(content):
    issues = []
    for term, replacement in LEGACY_TERMS.items():
        if term in content:
            issues.append(f"Found legacy term '{term}', consider replacing with '{replacement}'")
    return issues

def validate_structure(file_path, content):
    issues = []
    # Check for title
    lines = content.splitlines()
    has_title = False
    for line in lines:
        if line.strip().startswith("# "):
            has_title = True
            break
        if line.strip().startswith("---"): # skip frontmatter
            continue

    if not has_title:
        issues.append("Missing H1 title (# Title)")

    return issues

def main():
    files = get_files_in_scope()
    report = {}

    all_files = set(f.resolve() for f in files)

    for f in files:
        try:
            content = f.read_text()
        except UnicodeDecodeError:
            print(f"Skipping binary/non-utf8 file: {f}")
            continue

        file_issues = []
        file_issues.extend(validate_structure(f, content))
        file_issues.extend(validate_links(f, content, all_files))
        file_issues.extend(validate_legacy_terms(content))

        if file_issues:
            report[str(f)] = file_issues

    # Output report
    print("# Validation Report")
    for f, issues in report.items():
        print(f"\n## {f}")
        for issue in issues:
            print(f"- {issue}")

if __name__ == "__main__":
    main()
