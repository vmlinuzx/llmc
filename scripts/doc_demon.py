#!/usr/bin/env python3
"""
Documentation Demon - Quality & Accuracy Checker.
"""

import os
import re
import ast
import sys
import time
import argparse
import subprocess
from pathlib import Path
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown as RichMarkdown

try:
    from scripts.generate_cli_docs import CLI_COMMANDS
except ImportError:
    # Fallback if import fails (e.g. run from wrong dir)
    CLI_COMMANDS = [
        ("llmc-cli", "llmc.main", "Primary CLI for LLMC operations"),
        ("llmc-mcp", "llmc_mcp.cli", "MCP server for Claude Desktop integration"),
        ("te", "llmc.te.cli", "Tool Envelope - intelligent command wrapper"),
        ("llmc-chat", "llmc_agent.cli", "Chat agent CLI (also: bx)"),
        ("mcgrep", "llmc.mcgrep", "Semantic grep with RAG context"),
    ]

console = Console()

class DocDemon:
    def __init__(self, root_dir: Path):
        self.root = root_dir.resolve()
        self.docs_dir = self.root / "DOCS"
        self.readme = self.root / "README.md"
        self.issues = []

        if not self.docs_dir.exists():
            console.print(f"[red]Error: DOCS directory not found at {self.docs_dir}[/red]")
            sys.exit(1)

    def report_issue(self, check_name, file_path, message, level="error"):
        self.issues.append({
            "check": check_name,
            "file": str(file_path.relative_to(self.root) if file_path else "N/A"),
            "message": message,
            "level": level
        })

    def run_all(self):
        with console.status("[bold green]Running Documentation Demon...[/bold green]"):
            self.check_broken_links()
            self.check_code_examples()
            self.check_orphans()
            self.check_readme()
            self.check_cli_drift()
            self.check_stale_images()

        self.print_report()

    def check_broken_links(self):
        """Check for internal doc links that 404."""
        # Regex for Markdown links: [text](url) and [ref]: url
        # Handles images ![]() too as they match []() pattern if we don't exclude !
        # But we want to check image existence too.
        link_pattern = re.compile(r'!?\[([^\]]+)\]\(([^)]+)\)')
        ref_pattern = re.compile(r'^\[([^\]]+)\]:\s*(\S+)', re.MULTILINE)

        for md_file in self.docs_dir.rglob("*.md"):
            try:
                content = md_file.read_text()
            except Exception as e:
                self.report_issue("Broken Links", md_file, f"Could not read file: {e}")
                continue

            links = link_pattern.findall(content)
            refs = ref_pattern.findall(content)

            all_links = [url for _, url in links] + [url for _, url in refs]

            for url in all_links:
                url = url.split('#')[0] # Ignore anchors for file existence check
                if not url:
                    continue

                if url.startswith(('http://', 'https://', 'mailto:', 'ftp://')):
                    continue

                # Handle absolute path from root (rare but possible) or relative
                if url.startswith('/'):
                    target = self.root / url.lstrip('/')
                else:
                    target = (md_file.parent / url).resolve()

                # Security/Scope check: target should be inside root
                try:
                    target.relative_to(self.root)
                except ValueError:
                    # Pointing outside repo is technically okay if it exists, but might be unintended
                    pass

                if not target.exists():
                    self.report_issue("Broken Links", md_file, f"Dead link: {url}")
                elif target.is_dir() and not url.endswith('/'):
                    # Maybe linking to a dir without slash? Not strictly broken but good to know
                    pass

    def check_code_examples(self):
        """Check if Python code examples are syntactically valid."""
        # Regex to find python blocks
        code_block_pattern = re.compile(r'```python\s+(.*?)```', re.DOTALL)

        for md_file in self.docs_dir.rglob("*.md"):
            content = md_file.read_text()
            blocks = code_block_pattern.findall(content)

            for i, block in enumerate(blocks):
                try:
                    ast.parse(block)
                except SyntaxError as e:
                    self.report_issue("Code Example Validity", md_file, f"Syntax Error in block {i+1}: {e}")

    def check_orphans(self):
        """Find files not linked from anywhere."""
        all_md_files = set(self.docs_dir.rglob("*.md"))
        linked_files = set()

        # Link pattern again
        link_pattern = re.compile(r'!?\[([^\]]+)\]\(([^)]+)\)')

        for md_file in all_md_files:
            content = md_file.read_text()
            links = link_pattern.findall(content)
            for _, url in links:
                url = url.split('#')[0]
                if not url or url.startswith(('http', 'mailto')):
                    continue

                try:
                    target = (md_file.parent / url).resolve()
                    if target in all_md_files:
                        linked_files.add(target)
                except Exception:
                    pass

        # Add index.md as always linked (it's the entry)
        index = self.docs_dir / "index.md"
        if index in all_md_files:
            linked_files.add(index)

        orphans = all_md_files - linked_files
        for orphan in orphans:
            self.report_issue("Orphan Docs", orphan, "File is not linked from any other documentation file", level="warning")

    def check_readme(self):
        """Check README for installation steps."""
        if not self.readme.exists():
            self.report_issue("README Accuracy", self.readme, "README.md missing")
            return

        content = self.readme.read_text()

        # Check for pip install
        if "pip install" not in content and "curl" not in content:
            self.report_issue("README Accuracy", self.readme, "No obvious install instruction found (pip install / curl)")

        # Check if linked DOCS exist
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        links = link_pattern.findall(content)
        for text, url in links:
            if url.startswith('DOCS/'):
                target = self.root / url
                if not target.exists():
                    self.report_issue("README Accuracy", self.readme, f"Broken link to docs: {url}")

    def check_cli_drift(self):
        """Check for drift between --help and docs."""
        cli_ref_dir = self.docs_dir / "reference/cli"
        if not cli_ref_dir.exists():
            return # Skip if no CLI docs

        for cmd, module, _ in CLI_COMMANDS:
            # Get current help
            try:
                res = subprocess.run([cmd, "--help"], capture_output=True, text=True, timeout=5)
                if res.returncode != 0:
                    self.report_issue("CLI Drift", None, f"Command '{cmd}' failed to run: {res.stderr}", level="warning")
                    continue
                current_help = res.stdout.strip()
            except FileNotFoundError:
                 self.report_issue("CLI Drift", None, f"Command '{cmd}' not found in PATH", level="warning")
                 continue
            except Exception as e:
                 self.report_issue("CLI Drift", None, f"Error running '{cmd}': {e}", level="warning")
                 continue

            # Read doc
            doc_file = cli_ref_dir / f"{cmd}.md"
            if not doc_file.exists():
                self.report_issue("CLI Drift", doc_file, f"Missing documentation for command '{cmd}'")
                continue

            doc_content = doc_file.read_text()

            # Simple heuristic: check if first few lines of help are present in doc
            # We assume "Usage" block contains the help

            # Normalize for comparison (remove whitespace variations)
            def normalize(text):
                return re.sub(r'\s+', ' ', text).strip()

            # Extract help block from doc - look for text inside ```text and ```
            # This matches generate_cli_docs.py format
            match = re.search(r'```text\n(.*?)\n```', doc_content, re.DOTALL)
            if not match:
                self.report_issue("CLI Drift", doc_file, f"Could not find help block in documentation for '{cmd}'")
                continue

            doc_help = match.group(1).strip()

            # Check first line
            current_first = current_help.split('\n')[0]
            if current_first not in doc_help:
                 self.report_issue("CLI Drift", doc_file, f"Help output seems different from documentation for '{cmd}'.\nExpected start: {current_first}", level="warning")

    def check_stale_images(self):
        """Check for potentially stale screenshots (older than 90 days)."""
        image_pattern = re.compile(r'!\[.*?\]\((.*?)\)')

        # Heuristic: 90 days
        limit_seconds = 90 * 24 * 3600
        now = time.time()

        for md_file in self.docs_dir.rglob("*.md"):
            content = md_file.read_text()
            images = image_pattern.findall(content)

            for url in images:
                url = url.split('#')[0]
                if url.startswith(('http', 'mailto', 'ftp')):
                    continue

                # Resolve path
                if url.startswith('/'):
                    target = self.root / url.lstrip('/')
                else:
                    target = (md_file.parent / url).resolve()

                if target.exists() and target.is_file():
                    mtime = target.stat().st_mtime
                    age = now - mtime
                    if age > limit_seconds:
                        days = int(age / (24 * 3600))
                        self.report_issue("Stale Screenshots", md_file, f"Image '{url}' is {days} days old. Verify if it matches current UI.", level="warning")

    def print_report(self):
        table = Table(title="Documentation Demon Report")
        table.add_column("Check", style="cyan")
        table.add_column("File", style="magenta")
        table.add_column("Message", style="white")
        table.add_column("Level", style="red")

        error_count = 0

        for issue in self.issues:
            style = "red" if issue['level'] == "error" else "yellow"
            table.add_row(issue['check'], issue['file'], issue['message'], issue['level'], style=style)
            if issue['level'] == "error":
                error_count += 1

        console.print(table)

        if error_count > 0:
            console.print(f"\n[bold red]Found {error_count} errors.[/bold red]")
            sys.exit(1)
        else:
            console.print("\n[bold green]All checks passed![/bold green]")
            sys.exit(0)

def main():
    root = os.environ.get("LLMC_ROOT", ".")
    demon = DocDemon(Path(root))
    demon.run_all()

if __name__ == "__main__":
    main()
