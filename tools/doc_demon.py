#!/usr/bin/env python3
import os
import re
import sys
import ast
import subprocess
from pathlib import Path
from collections import deque

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import print as rprint
    console = Console()
except ImportError:
    console = None
    def rprint(*args, **kwargs):
        # Strip rich tags if console is not available
        msg = " ".join(str(arg) for arg in args)
        msg = re.sub(r'\[.*?\]', '', msg)
        print(msg)

# --- Configuration ---
ROOT_DIR = Path(os.environ.get("LLMC_ROOT", os.getcwd())).resolve()
DOCS_DIR = ROOT_DIR / "DOCS"
# Add root to sys.path to import scripts
sys.path.insert(0, str(ROOT_DIR))

try:
    from scripts.generate_cli_docs import CLI_COMMANDS
except ImportError:
    # Fallback if import fails
    CLI_COMMANDS = [
        ("llmc-cli", "llmc.main", "Primary CLI for LLMC operations"),
        ("llmc-mcp", "llmc_mcp.cli", "MCP server for Claude Desktop integration"),
        ("te", "llmc.te.cli", "Tool Envelope - intelligent command wrapper"),
        ("llmc-chat", "llmc_agent.cli", "Chat agent CLI (also: bx)"),
        ("mcgrep", "llmc.mcgrep", "Semantic grep with RAG context"),
    ]

class DocDemon:
    def __init__(self):
        self.broken_links = []
        self.invalid_examples = []
        self.cli_drifts = []
        self.readme_issues = []
        self.orphans = []
        self.stale_screenshots = []
        self.checked_files = 0

    def run(self):
        if console:
            console.rule("[bold red]Documentation Demon")
        else:
            print("--- Documentation Demon ---")

        self.check_broken_links()
        self.check_code_validity()
        self.check_cli_drift()
        self.check_readme()
        self.check_orphans()
        self.check_screenshots()

        self.report()

    def check_broken_links(self):
        rprint("[bold blue]Checking for Broken Links...[/bold blue]")
        for md_file in DOCS_DIR.rglob("*.md"):
            self.checked_files += 1
            content = md_file.read_text(encoding="utf-8")
            # Regex for [text](link)
            links = re.findall(r'\[.*?\]\((.*?)\)', content)
            for link in links:
                # Ignore external links and anchors
                if link.startswith(('http', 'https', 'mailto:', '#')):
                    continue

                # Handle anchor part in file path
                link_path = link.split('#')[0]
                if not link_path:
                    continue

                target = (md_file.parent / link_path).resolve()
                if not target.exists():
                    self.broken_links.append((str(md_file.relative_to(ROOT_DIR)), link))

    def check_code_validity(self):
        rprint("[bold blue]Checking Code Validity...[/bold blue]")
        for md_file in DOCS_DIR.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            # Find python blocks
            blocks = re.findall(r'```python\n(.*?)\n```', content, re.DOTALL)
            for i, block in enumerate(blocks):
                try:
                    ast.parse(block)
                except SyntaxError as e:
                    self.invalid_examples.append((str(md_file.relative_to(ROOT_DIR)), i+1, str(e)))

    def check_cli_drift(self):
        rprint("[bold blue]Checking CLI Drift...[/bold blue]")
        for cmd_name, module, _ in CLI_COMMANDS:
            # Get help text
            help_text = self._get_help_text(cmd_name, module)
            if not help_text:
                self.cli_drifts.append((cmd_name, "Could not run --help"))
                continue

            # Find doc file
            # Assuming standard location
            doc_path = DOCS_DIR / "reference" / "cli" / f"{cmd_name}.md"
            if not doc_path.exists():
                self.cli_drifts.append((cmd_name, f"Doc file missing: {doc_path}"))
                continue

            doc_content = doc_path.read_text(encoding="utf-8")

            if "Usage:" in help_text:
                usage_lines = [l for l in help_text.splitlines() if "Usage:" in l]
                if usage_lines:
                    usage_line = usage_lines[0].strip()
                    # Check if usage line is present (ignoring whitespace differences)
                    if not self._fuzzy_contains(doc_content, usage_line):
                         self.cli_drifts.append((cmd_name, f"Usage line not found in docs: {usage_line}"))

    def _fuzzy_contains(self, text, substring):
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        substring = re.sub(r'\s+', ' ', substring)
        return substring in text

    def _get_help_text(self, cmd_name, module):
        # Try running command
        try:
            res = subprocess.run([cmd_name, "--help"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return res.stdout
        except (FileNotFoundError, OSError):
            pass

        # Try python -m module
        try:
            res = subprocess.run([sys.executable, "-m", module, "--help"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return res.stdout
        except Exception as e:
            return None
        return None

    def check_readme(self):
        rprint("[bold blue]Checking README Accuracy...[/bold blue]")
        readme_path = ROOT_DIR / "README.md"
        if not readme_path.exists():
            self.readme_issues.append("README.md missing")
            return

        content = readme_path.read_text(encoding="utf-8")
        # Check for install command
        if "pip install" not in content and "install.sh" not in content:
            self.readme_issues.append("No installation instructions found")

        # Basic check: verify if mentioned files exist
        links = re.findall(r'\[.*?\]\((.*?)\)', content)
        for link in links:
             if link.startswith(('http', '#', 'mailto:')): continue
             target = (ROOT_DIR / link).resolve()
             if not target.exists():
                 self.readme_issues.append(f"Broken link in README: {link}")

    def check_orphans(self):
        rprint("[bold blue]Checking for Orphan Docs...[/bold blue]")
        all_docs = set(str(p.relative_to(DOCS_DIR)) for p in DOCS_DIR.rglob("*.md"))
        referenced_docs = set()

        # Start BFS from index.md
        if not (DOCS_DIR / "index.md").exists():
             self.orphans = list(all_docs)
             return

        queue = deque(["index.md"])
        referenced_docs.add("index.md")

        while queue:
            current = queue.popleft()
            curr_path = DOCS_DIR / current
            if not curr_path.exists():
                continue

            content = curr_path.read_text(encoding="utf-8")
            links = re.findall(r'\[.*?\]\((.*?)\)', content)

            curr_dir = curr_path.parent

            for link in links:
                if link.startswith(('http', '#', 'mailto:')): continue

                # Clean link (remove anchor)
                link_clean = link.split('#')[0]
                if not link_clean: continue
                if not link_clean.endswith('.md'): continue

                # Resolve link
                target_path = (curr_dir / link_clean).resolve()
                try:
                    rel_target = target_path.relative_to(DOCS_DIR)
                    if str(rel_target) not in referenced_docs:
                        referenced_docs.add(str(rel_target))
                        queue.append(str(rel_target))
                except ValueError:
                    # Link points outside DOCS/
                    pass

        self.orphans = list(all_docs - referenced_docs)

    def check_screenshots(self):
        rprint("[bold blue]Checking Screenshots...[/bold blue]")
        # Check image existence
        for md_file in DOCS_DIR.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            images = re.findall(r'!\[.*?\]\((.*?)\)', content)
            for img in images:
                if img.startswith('http'): continue
                target = (md_file.parent / img).resolve()
                if not target.exists():
                    self.stale_screenshots.append((str(md_file.relative_to(ROOT_DIR)), img, "Missing file"))

    def report(self):
        if console:
            console.rule("[bold red]Report")
        else:
            print("\n--- Report ---")

        if self.broken_links:
            rprint(f"\n[bold red]Broken Links ({len(self.broken_links)}):[/bold red]")
            for f, l in self.broken_links:
                rprint(f"  {f}: {l}")
        else:
             rprint("\n[green]No broken links found.[/green]")

        if self.invalid_examples:
            rprint(f"\n[bold red]Invalid Code Examples ({len(self.invalid_examples)}):[/bold red]")
            for f, n, e in self.invalid_examples:
                rprint(f"  {f} (block {n}): {e}")
        else:
             rprint("\n[green]All code examples are valid syntax.[/green]")

        if self.cli_drifts:
            rprint(f"\n[bold red]CLI Drift ({len(self.cli_drifts)}):[/bold red]")
            for c, m in self.cli_drifts:
                rprint(f"  {c}: {m}")
        else:
             rprint("\n[green]CLI Docs appear consistent.[/green]")

        if self.readme_issues:
             rprint(f"\n[bold red]README Issues ({len(self.readme_issues)}):[/bold red]")
             for i in self.readme_issues:
                 rprint(f"  {i}")
        else:
             rprint("\n[green]README looks good.[/green]")

        if self.orphans:
            rprint(f"\n[bold red]Orphan Docs ({len(self.orphans)}):[/bold red]")
            for o in self.orphans:
                rprint(f"  {o}")
        else:
             rprint("\n[green]No orphan docs found.[/green]")

        if self.stale_screenshots:
            rprint(f"\n[bold red]Stale/Missing Screenshots ({len(self.stale_screenshots)}):[/bold red]")
            for f, i, m in self.stale_screenshots:
                rprint(f"  {f}: {i} ({m})")
        else:
             rprint("\n[green]All screenshot files exist.[/green]")

if __name__ == "__main__":
    DocDemon().run()
