#!/usr/bin/env python3
"""
Native Tool Scripts Demo

Demonstrates the OpenAI/Anthropic/MCP-compatible tool scripts.
Run from repo root: python3 scripts/demo_native_tools.py
"""
import json
from pathlib import Path
import subprocess

# Colors for terminal
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def header(text: str):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")


def subheader(text: str):
    print(f"\n{YELLOW}>>> {text}{RESET}\n")


def run_tool(script_path: str, args: dict, description: str = ""):
    """Run a tool script and display results."""
    repo_root = Path(__file__).resolve().parent.parent
    
    if description:
        print(f"{BOLD}{description}{RESET}")
    
    cmd = f"./{script_path} '{json.dumps(args)}'"
    print(f"{BLUE}$ {cmd}{RESET}")
    
    try:
        result = subprocess.run(
            [str(repo_root / script_path), json.dumps(args)],
            check=False, capture_output=True,
            text=True,
            cwd=str(repo_root),
            timeout=30,
        )
        
        output = json.loads(result.stdout)
        success = output.get("success", False)
        
        if success:
            print(f"{GREEN}✓ Success{RESET}")
        else:
            print(f"{RED}✗ Failed: {output.get('error', 'Unknown')}{RESET}")
        
        # Pretty print (truncated for readability)
        formatted = json.dumps(output, indent=2)
        if len(formatted) > 1500:
            formatted = formatted[:1500] + "\n... (truncated)"
        print(formatted)
        print()
        return output
        
    except subprocess.TimeoutExpired:
        print(f"{RED}✗ Timeout{RESET}\n")
        return {"success": False, "error": "timeout"}
    except json.JSONDecodeError as e:
        print(f"{RED}✗ Invalid JSON: {e}{RESET}")
        print(f"stdout: {result.stdout[:500]}")
        print()
        return {"success": False, "error": str(e)}
    except Exception as e:
        print(f"{RED}✗ Error: {e}{RESET}\n")
        return {"success": False, "error": str(e)}


def main():
    header("Native Tool Scripts Demo")
    print("This demo shows OpenAI/Anthropic/MCP-compatible tool scripts.")
    print("All tools use JSON in, JSON out interface.\n")
    
    # ========================================
    # OpenAI Tools
    # ========================================
    header("1. OpenAI Tools (scripts/openaitools/)")
    
    subheader("file_search - Semantic RAG Search with LLMC Enrichment")
    run_tool(
        "scripts/openaitools/file_search",
        {"query": "router configuration", "limit": 2, "include_content": True},
        "Search for 'router configuration' with code snippets:"
    )
    
    # ========================================
    # MCP Tools  
    # ========================================
    header("2. MCP Tools (scripts/mcptools/)")
    
    subheader("read_text_file - Read file with head/tail")
    run_tool(
        "scripts/mcptools/read_text_file",
        {"path": "README.md", "head": 15},
        "Read first 15 lines of README.md:"
    )
    
    subheader("list_directory - List with [FILE]/[DIR] prefixes")
    run_tool(
        "scripts/mcptools/list_directory",
        {"path": "scripts/mcptools"},
        "List MCP tools directory:"
    )
    
    subheader("search_files - Recursive glob search")
    run_tool(
        "scripts/mcptools/search_files",
        {"path": "scripts", "pattern": "*.py", "excludePatterns": ["__pycache__"]},
        "Find all Python files in scripts/:"
    )
    
    subheader("edit_file - Dry run str_replace")
    # Create a temp file for editing demo
    repo_root = Path(__file__).resolve().parent.parent
    temp_file = repo_root / "scripts" / "_demo_temp.txt"
    temp_file.write_text("Hello World\nThis is a test file.\n", encoding="utf-8")
    
    run_tool(
        "scripts/mcptools/edit_file",
        {
            "path": "scripts/_demo_temp.txt",
            "edits": [{"oldText": "Hello World", "newText": "Hello LLMC"}],
            "dryRun": True
        },
        "Preview edit (dry run):"
    )
    temp_file.unlink()  # Clean up
    
    # ========================================
    # Anthropic Tools
    # ========================================
    header("3. Anthropic Tools (scripts/anthropictools/)")
    
    subheader("bash - Shell command execution")
    run_tool(
        "scripts/anthropictools/bash",
        {"command": "echo 'Hello from bash!' && date"},
        "Execute shell command:"
    )
    
    subheader("text_editor - View file with line numbers")
    run_tool(
        "scripts/anthropictools/text_editor",
        {"command": "view", "path": "README.md", "view_range": [1, 15]},
        "View lines 1-15 of README.md:"
    )
    
    # ========================================
    # Security Demo
    # ========================================
    header("4. Security Features")
    
    subheader("Path containment - blocks access outside allowed roots")
    run_tool(
        "scripts/mcptools/read_text_file",
        {"path": "/etc/passwd"},
        "Attempt to read /etc/passwd (should fail):"
    )
    
    subheader("Dangerous command blocking")
    run_tool(
        "scripts/anthropictools/bash",
        {"command": "rm -rf /"},
        "Attempt dangerous command (should fail):"
    )
    
    # ========================================
    # Summary
    # ========================================
    header("Summary")
    print(f"""
{BOLD}Implemented Tools:{RESET}

{GREEN}OpenAI Tools:{RESET}
  • file_search - Semantic RAG with graph context + enrichment

{GREEN}MCP Tools:{RESET}
  • read_text_file - UTF-8 file read with head/tail
  • write_file - Create/overwrite files
  • list_directory - [FILE]/[DIR] prefixed listing
  • edit_file - str_replace pattern editing
  • search_files - Recursive glob search

{GREEN}Anthropic Tools:{RESET}
  • bash - Shell execution with security
  • text_editor - view/create/str_replace/insert

{GREEN}LLMC Tools:{RESET}
  • mcgrep, mcwho (symlinks to llmc CLIs)

{BOLD}Key Features:{RESET}
  • JSON in, JSON out (LLM-friendly)
  • Path containment security
  • LLMC RAG enrichment (graph, summaries, pitfalls)
  • Compatible with local models (Qwen) and MCP servers
""")


if __name__ == "__main__":
    main()
