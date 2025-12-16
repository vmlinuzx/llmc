#!/usr/bin/env python3
import subprocess
import os
import sys

# Map command names to output files
COMMANDS = {
    "llmc-rag-repo": "llmc-rag-repo.md",
    "llmc-rag-service": "llmc-rag-service.md",
    "llmc-rag-daemon": "llmc-rag-daemon.md",
    # llmc-mcp might need to be run as a module if not in path, but let's try module first for all
    "tools.rag_repo.cli": "llmc-rag-repo.md",
    "tools.rag.service": "llmc-rag-service.md", 
    "tools.rag_daemon.main": "llmc-rag-daemon.md",
    "llmc_mcp.server": "llmc-mcp.md"
}

# We will prefer running as module to avoid PATH issues
MODULE_MAP = {
    "llmc-rag-repo": "tools.rag_repo.cli",
    "llmc-rag-service": "tools.rag.service", # Note: service is usually a script wrapper around tools.rag.service or similar
    "llmc-rag-daemon": "tools.rag_daemon.main",
    "llmc-mcp": "llmc_mcp.cli" # Guessing the module path
}

OUTPUT_DIR = "DOCS/reference/cli"

def run_help(module_name):
    try:
        cmd = [sys.executable, "-m", module_name, "--help"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout
    except Exception as e:
        return f"Error generating docs: {e}"

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # Let's verify module paths by looking at the file structure if needed.
    # I'll stick to the ones I saw in the file list earlier.
    # tools.rag_repo.cli -> Yes
    # tools.rag_daemon.main -> Yes
    # tools.rag.service -> Wait, list showed llmc/tools/rag/service? No, tools/rag/service.py?
    # Let's double check content.
    
    modules = [
        ("tools.rag_repo.cli", "llmc-rag-repo.md"),
        ("tools.rag_daemon.main", "llmc-rag-daemon.md"),
        ("tools.rag.cli", "llmc-rag-cli.md"), # Adding the main rag CLI
        ("llmc_mcp.cli", "llmc-mcp.md")
    ]

    for module, filename in modules:
        print(f"Generating docs for {module}...")
        help_text = run_help(module)
        
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "w") as f:
            f.write(f"# {filename.replace('.md', '')} Reference\n\n")
            f.write(f"Generated from `{module} --help`\n\n")
            f.write("```text\n")
            f.write(help_text)
            f.write("```\n")
        print(f"Wrote {filepath}")

if __name__ == "__main__":
    main()
