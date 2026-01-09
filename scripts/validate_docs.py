import os
import re
import sys
from pathlib import Path

# Configuration
DOCS_ROOT = Path("DOCS")
SCOPE_DIRS = [
    "getting-started",
    "user-guide",
    "operations",
    "architecture",
    "reference",
    "development"
]

DEPRECATED_TERMS = [
    "tools.rag",
    "llmc-rag-repo",
    "llmc-rag-daemon",
    "llmc-rag-cli"
]

# Regex patterns
LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
TITLE_PATTERN = re.compile(r'^#\s+(.+)', re.MULTILINE)
FRONTMATTER_PATTERN = re.compile(r'^---\s*\n', re.MULTILINE)

class doc_issue:
    def __init__(self, file, issue_type, details):
        self.file = file
        self.issue_type = issue_type
        self.details = details

    def __str__(self):
        return f"[{self.issue_type}] {self.file}: {self.details}"

def validate_file(file_path, repo_root):
    issues = []
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return [doc_issue(file_path, "READ_ERROR", str(e))]

    # 1. Check Title/Frontmatter
    has_frontmatter = FRONTMATTER_PATTERN.match(content)
    has_title = TITLE_PATTERN.search(content)

    if not has_frontmatter and not has_title:
        issues.append(doc_issue(file_path, "STRUCTURE", "Missing H1 title or frontmatter"))

    # 2. Check Links
    for match in LINK_PATTERN.finditer(content):
        link_text = match.group(1)
        link_target = match.group(2)

        # Skip external links
        if link_target.startswith(('http://', 'https://', 'mailto:')):
            continue

        # Handle anchors
        anchor = None
        if '#' in link_target:
            link_target, anchor = link_target.split('#', 1)

        if not link_target:
            # internal anchor only, skip for now
            continue

        # Resolve path
        target_path = None
        if link_target.startswith('/'):
             # Relative to repo root
             target_path = repo_root / link_target.lstrip('/')
        else:
             # Relative to current file
             target_path = (file_path.parent / link_target).resolve()

        # Check if file exists
        try:
            if not target_path.exists():
                issues.append(doc_issue(file_path, "BROKEN_LINK", f"Target not found: {link_target} (resolved: {target_path})"))
        except Exception as e:
             issues.append(doc_issue(file_path, "LINK_ERROR", f"Error checking link {link_target}: {e}"))

    # 3. Check Deprecated Terms
    for term in DEPRECATED_TERMS:
        if term in content:
             # exceptions for legacy docs or migration guides could be added here
             issues.append(doc_issue(file_path, "DEPRECATED", f"Found deprecated term: {term}"))

    return issues

def main():
    repo_root = Path.cwd()
    all_issues = []

    files_to_check = []
    for scope_dir in SCOPE_DIRS:
        dir_path = DOCS_ROOT / scope_dir
        if dir_path.exists():
            files_to_check.extend(dir_path.rglob("*.md"))

    print(f"Scanning {len(files_to_check)} files...")

    for file_path in files_to_check:
        # Resolve file_path to absolute to allow consistent relative_to calls later if needed,
        # but keep track of it relative to CWD for printing if preferred.
        abs_file_path = file_path.resolve()
        all_issues.extend(validate_file(abs_file_path, repo_root))

    # Group issues by type
    if not all_issues:
        print("✅ No issues found.")
        return 0

    print(f"\n⚠️ Found {len(all_issues)} issues:\n")

    current_file = None
    for issue in sorted(all_issues, key=lambda x: str(x.file)):
        if issue.file != current_file:
            try:
                display_path = issue.file.relative_to(repo_root)
            except ValueError:
                display_path = issue.file
            print(f"\n📄 {display_path}")
            current_file = issue.file
        print(f"  - [{issue.issue_type}] {issue.details}")

if __name__ == "__main__":
    main()
