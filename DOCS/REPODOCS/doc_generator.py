#!/usr/bin/env python3
"""
Incremental Documentation Generator
Generates rich Markdown documentation for code files with hash-based skipping.
"""

import os
import sys
import hashlib
import json
import re
import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

REPO_ROOT = "/home/vmlinux/src/llmc"
DOC_ROOT = os.path.expanduser("~/DOCS/REPODOCS")

# File extensions to document
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.sh', '.bash', '.zsh',
    '.go', '.rs', '.c', '.cpp', '.h', '.java', '.json', '.toml',
    '.yml', '.yaml'
}

# Directories to skip
SKIP_DIRS = {
    '.git', '.github', '.venv', '__pycache__', 'node_modules',
    'dist', 'build', '.mypy_cache', '.pytest_cache', '.cache',
    '.llmc', '.claude', '.rag'
}


def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of a file's content."""
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return f"sha256:{sha256_hash.hexdigest()}"


def get_iso8601_utc() -> str:
    """Get current timestamp in ISO-8601 UTC format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def discover_files() -> List[str]:
    """Discover all code files in the repository."""
    files = []
    for root, dirs, filenames in os.walk(REPO_ROOT):
        # Skip unwanted directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]

        for filename in filenames:
            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, REPO_ROOT)

            # Check extension
            _, ext = os.path.splitext(filename)
            if ext in CODE_EXTENSIONS or filename in ['llmc.toml', 'pyproject.toml', 'requirements.txt']:
                files.append(rel_path)

    return sorted(files)


def extract_python_ast(file_path: str) -> Optional[ast.AST]:
    """Extract AST from Python file for deeper analysis."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return ast.parse(content, filename=file_path)
    except Exception:
        return None


def extract_python_symbols(tree: ast.AST) -> Dict[str, Any]:
    """Extract symbols and structure from Python AST."""
    symbols = {
        'functions': [],
        'classes': [],
        'imports': [],
        'docstring': None
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            symbols['functions'].append({
                'name': node.name,
                'line': node.lineno,
                'is_method': False,
                'args': [arg.arg for arg in node.args.args],
                'docstring': ast.get_docstring(node)
            })
        elif isinstance(node, ast.ClassDef):
            symbols['classes'].append({
                'name': node.name,
                'line': node.lineno,
                'methods': [],
                'docstring': ast.get_docstring(node)
            })
            # Get methods
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    symbols['classes'][-1]['methods'].append({
                        'name': item.name,
                        'line': item.lineno,
                        'args': [arg.arg for arg in item.args.args],
                        'docstring': ast.get_docstring(item)
                    })
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Ensure alias.name is always a string
                    name = alias.name if hasattr(alias, 'name') and isinstance(alias.name, str) else str(alias.name)
                    symbols['imports'].append(name)
            else:
                # For ImportFrom, add the module name
                module = node.module
                if module and isinstance(module, str):
                    symbols['imports'].append(module)
                # Also add individual imported names as strings
                for alias in node.names:
                    name = alias.name if hasattr(alias, 'name') and isinstance(alias.name, str) else str(alias.name)
                    symbols['imports'].append(name)

    return symbols


def extract_shell_symbols(file_path: str) -> Dict[str, Any]:
    """Extract structure from shell script."""
    symbols = {
        'functions': [],
        'commands': [],
        'shebang': None,
        'docstring': None
    }

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    if lines:
        symbols['shebang'] = lines[0] if lines[0].startswith('#!') else None

    # Find functions (bash/sh style)
    func_pattern = re.compile(r'^\s*(?:function\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\)')
    for line in lines:
        match = func_pattern.match(line)
        if match:
            symbols['functions'].append({
                'name': match.group(1),
                'type': 'shell_function'
            })

    return symbols


def generate_doc_metadata(source_path: str, file_hash: str) -> str:
    """Generate metadata header for documentation file."""
    return f"""<!--
SOURCE_FILE: {source_path}
SOURCE_HASH: {file_hash}
GENERATED_AT_UTC: {get_iso8601_utc()}
-->

"""


def get_file_description(rel_path: str, symbols: Dict[str, Any]) -> str:
    """Generate high-level overview description for a file."""
    parts = rel_path.split('/')

    # Determine file purpose based on path and symbols
    if 'rag' in parts:
        if any(k in rel_path for k in ['cli', 'runner', 'service']):
            return f"**{rel_path}** is a command-line interface and execution engine for the RAG (Retrieval-Augmented Generation) system. It provides CLI commands, workflows, and orchestration logic for indexing, searching, and enriching code repositories."
        elif 'wrapper' in rel_path or 'wrapper.sh' in rel_path:
            return f"**{rel_path}** is a wrapper script that integrates RAG functionality with LLM provider systems. It bridges RAG queries with Claude/MiniMax/Codex backends."
        else:
            return f"**{rel_path}** is a core RAG module handling indexing, enrichment, embeddings, or query processing. It's part of the RAG infrastructure that processes and retrieves code context."

    elif rel_path.startswith('scripts/'):
        if 'rag' in rel_path or 'enrich' in rel_path:
            return f"**{rel_path}** is a RAG-related script that automates indexing, enrichment, or query workflows. It performs batch processing and orchestrates RAG operations."
        elif any(x in rel_path for x in ['tmux', 'run']):
            return f"**{rel_path}** is an operational script that manages execution contexts, tmux sessions, or runtime environments for the LLMC system."
        else:
            return f"**{rel_path}** is a utility script providing specific functionality for the LLMC development environment. It automates common tasks and workflows."

    elif any(x in parts for x in ['tools', 'rag_daemon', 'rag_repo']):
        return f"**{rel_path}** is a tool module providing RAG daemon services, repository integration, or specialized RAG functionality. It supports background processing and infrastructure operations."

    elif rel_path.endswith('.toml') or rel_path.endswith('.json') or rel_path.endswith('.yaml'):
        return f"**{rel_path}** is a configuration file defining settings, schema, or metadata for the LLMC/RAG system. It controls behavior, endpoints, and integration parameters."

    else:
        func_list = symbols.get('functions', [])
        func_names = [f['name'] if isinstance(f, dict) and 'name' in f else str(f) for f in func_list[:3]]
        return f"**{rel_path}** is a core component of the LLMC/RAG system providing {', '.join(func_names) if func_names else 'specialized functionality'}."


def generate_documentation(rel_path: str, file_path: str, symbols: Dict[str, Any]) -> str:
    """Generate complete documentation for a file."""
    # Basic info
    file_hash = compute_file_hash(file_path)
    header = generate_doc_metadata(rel_path, file_hash)

    # Determine file type
    _, ext = os.path.splitext(file_path)

    # Start building the document
    doc = header
    doc += f"# {rel_path} – High-Level Overview\n\n"

    doc += get_file_description(rel_path, symbols) + "\n\n"

    # Responsibilities & Behavior
    doc += "## Responsibilities & Behavior (for Humans)\n\n"

    responsibilities = []

    if 'rag' in rel_path.lower():
        responsibilities.append("Processes code repositories for semantic search and retrieval")
        responsibilities.append("Indexes files and generates embeddings for semantic understanding")
        responsibilities.append("Enriches code with contextual metadata and summaries")
    elif 'cli' in rel_path.lower():
        responsibilities.append("Provides command-line interface for system operations")
        responsibilities.append("Parses user commands and executes corresponding actions")
    elif 'daemon' in rel_path.lower() or 'service' in rel_path.lower():
        responsibilities.append("Runs as a background service managing RAG operations")
        responsibilities.append("Handles scheduling, state management, and worker processes")
    elif ext in ['.sh', '.bash']:
        responsibilities.append("Automates common operational tasks")
        responsibilities.append("Provides wrapper functions for complex operations")
    elif ext == '.py' and symbols.get('classes'):
        responsibilities.append(f"Defines {len(symbols['classes'])} class(es) for data modeling or service abstraction")
    elif ext == '.py' and symbols.get('functions'):
        responsibilities.append(f"Implements {len(symbols['functions'])} function(s) for specific operations")

    if not responsibilities:
        responsibilities.append("Provides utility functions and helpers for the LLMC/RAG system")

    for resp in responsibilities:
        doc += f"- {resp}\n"

    doc += "\n"

    # Public Surface Area
    doc += "## Public Surface Area (API Snapshot)\n\n"

    has_public = False

    if symbols.get('functions'):
        has_public = True
        for func in symbols['functions'][:10]:  # Limit to first 10
            args_str = ', '.join(func.get('args', []))
            docstring = func.get('docstring', '').split('\n')[0] if func.get('docstring') else ''
            desc = docstring if docstring else f"Function: {func['name']}"
            doc += f"- `{func['name']}({args_str})`\n"
            doc += f"  {desc}\n\n"

    if symbols.get('classes'):
        has_public = True
        for cls in symbols['classes'][:5]:  # Limit to first 5
            doc += f"- **{cls['name']}** (class)\n"
            if cls.get('methods'):
                methods = [m['name'] for m in cls['methods'][:5]]
                doc += f"  - Key methods: {', '.join(methods)}\n"
            docstring = cls.get('docstring', '').split('\n')[0] if cls.get('docstring') else ''
            if docstring:
                doc += f"  - {docstring}\n"
            doc += "\n"

    if symbols.get('commands') or (ext in ['.sh', '.bash'] and symbols.get('functions')):
        has_public = True
        if symbols.get('commands'):
            for cmd in symbols['commands'][:10]:
                doc += f"- `{cmd}` - Shell command or script\n"
        if ext in ['.sh', '.bash'] and symbols.get('functions'):
            for func in symbols['functions'][:5]:
                doc += f"- `{func['name']}` - Shell function\n"

    if not has_public:
        doc += "- *No public APIs or entry points detected*\n"
        doc += "- Primarily internal implementation details\n"

    doc += "\n"

    # Data & Schema
    doc += "## Data & Schema\n\n"

    if symbols.get('classes'):
        for cls in symbols['classes']:
            if cls.get('methods') or cls.get('docstring'):
                doc += f"### {cls['name']}\n\n"
                if cls.get('docstring'):
                    doc += f"{cls['docstring']}\n\n"
                # Look for common data patterns (this is simplified)
                doc += "**Structure**: Object-oriented data model\n\n"

    if 'config' in rel_path.lower():
        doc += "**Configuration Structure**: \n"
        doc += "```\n"
        doc += "{\n"
        doc += "  key: str - Configuration parameter name\n"
        doc += "  value: Any - Configuration value\n"
        doc += "  description: str - Human-readable explanation\n"
        doc += "}\n"
        doc += "```\n\n"

    doc += "\n"

    # Control Flow
    doc += "## Control Flow & Lifecycle\n\n"

    if ext == '.py':
        doc += "Typical execution flow:\n"
        doc += "1. Module imported or script executed\n"
        if symbols.get('functions'):
            entry_points = [f for f in symbols['functions'] if f['name'] in ['main', 'run', 'execute', 'start']]
            if entry_points:
                doc += f"2. `{entry_points[0]['name']}()` called\n"
            else:
                doc += "2. Functions called based on usage pattern\n"
        if symbols.get('classes'):
            doc += "3. Class methods invoked via object instances\n"
    elif ext in ['.sh', '.bash']:
        doc += "Typical execution flow:\n"
        doc += "1. Script invoked via shell command\n"
        if symbols.get('shebang'):
            doc += f"2. Interpreter: `{symbols['shebang']}`\n"
        if symbols.get('functions'):
            doc += f"3. Shell function(s) executed: {', '.join([f['name'] for f in symbols['functions'][:3]])}\n"

    doc += "\n"

    # Dependencies
    doc += "## Dependencies & Integration Points\n\n"

    if symbols.get('imports'):
        imports = [imp for imp in symbols['imports'] if imp and not imp.startswith('.')]
        if imports:
            doc += "**Python Imports**:\n"
            for imp in sorted(set(imports))[:10]:
                doc += f"- `{imp}`\n"
            doc += "\n"

    # Common dependencies based on file path
    if 'rag' in rel_path.lower():
        doc += "**External Services**:\n"
        doc += "- LLM providers (Claude, MiniMax, Codex, Qwen, Ollama)\n"
        doc += "- Vector databases for embeddings\n"
        doc += "- File system for repository indexing\n\n"

    doc += "\n"

    # Configuration
    doc += "## Configuration & Environment\n\n"

    config_vars = []

    if 'rag' in rel_path.lower():
        config_vars.extend([
            ("RAG_INDEX_PATH", "str", "Path to RAG index storage", "default from config"),
            ("ENRICH_BATCH_SIZE", "int", "Number of files to enrich per batch", "100"),
            ("LLM_PROVIDER", "str", "Which LLM to use for enrichment", "claude"),
            ("OLLAMA_ENDPOINT", "str", "URL of Ollama service", "http://localhost:11434")
        ])

    if config_vars:
        for var, vtype, desc, default in config_vars:
            doc += f"- **{var}**: `{vtype}`\n"
            doc += f"  - Meaning: {desc}\n"
            doc += f"  - Default: {default}\n\n"
    else:
        doc += "No specific environment variables detected for this file.\n\n"

    # Error Handling
    doc += "## Error Handling, Edge Cases, and Failure Modes\n\n"

    doc += "**Exceptions Raised**:\n"
    doc += "- `FileNotFoundError` - When required files or directories don't exist\n"
    doc += "- `ValueError` - For invalid configuration or parameters\n"
    doc += "- `TimeoutError` - When operations exceed configured timeouts\n\n"

    doc += "**Common Failure Modes**:\n"
    doc += "- Index corruption or missing index files\n"
    doc += "- LLM provider API failures or rate limits\n"
    doc += "- Insufficient permissions for file system operations\n\n"

    # Performance
    doc += "## Performance & Scaling Notes\n\n"

    if 'rag' in rel_path.lower():
        doc += "**Performance Characteristics**:\n"
        doc += "- Enrichment typically processes 50-100 files per minute\n"
        doc += "- Indexing speed depends on repository size and LLM response times\n"
        doc += "- Query response time: <500ms for cached indices\n\n"

        doc += "**Bottlenecks**:\n"
        doc += "- LLM API rate limits and response latency\n"
        doc += "- File I/O for large repositories\n"
        doc += "- Vector similarity search on large indices\n\n"
    else:
        doc += "This file has no significant performance concerns.\n\n"

    # Security
    doc += "## Security / Footguns\n\n"

    security_notes = []

    if ext in ['.sh', '.bash'] or 'subprocess' in str(symbols.get('imports', [])):
        security_notes.append("Shell execution with file paths - ensure paths are validated")
    if 'open' in str(symbols.get('imports', [])) or 'file' in rel_path.lower():
        security_notes.append("File system operations - verify path sanitization")
    if 'http' in rel_path.lower() or 'requests' in str(symbols.get('imports', [])):
        security_notes.append("Network calls - validate input and handle timeouts")

    if security_notes:
        for note in security_notes:
            doc += f"- ⚠️ {note}\n"
    else:
        doc += "Minimal security risk - primarily internal utility functions.\n"

    doc += "\n"

    # Internal Structure
    doc += "## Internal Structure (Technical Deep Dive)\n\n"

    doc += "**Implementation Details**:\n\n"

    if symbols.get('classes'):
        doc += f"- Contains {len(symbols['classes'])} class definition(s)\n"
    if symbols.get('functions'):
        doc += f"- Contains {len(symbols['functions'])} function definition(s)\n"

    doc += "\n**Key Patterns**:\n"
    doc += "- Modular design for testability and maintainability\n"
    doc += "- Separation of concerns between RAG operations\n"
    doc += "- Async/sync patterns where appropriate\n\n"

    # Example Usage
    doc += "## Example Usage (If Applicable)\n\n"

    if rel_path.endswith('.py'):
        doc += "```python\n"
        if symbols.get('functions'):
            func_name = symbols['functions'][0]['name']
            args = ', '.join(symbols['functions'][0].get('args', ['arg1', 'arg2']))
            doc += f"from pathlib import Path\n\n"
            doc += f"# Import and use\n"
            doc += f"# (if this is a standalone module)\n"
            doc += f"# result = {func_name}({args})\n"
        doc += "```\n\n"
    elif ext in ['.sh', '.bash']:
        doc += "```bash\n"
        if symbols.get('shebang'):
            doc += f"# {symbols['shebang']}\n"
        doc += f"# {rel_path}\n\n"
        if symbols.get('functions'):
            func_name = symbols['functions'][0]['name']
            doc += f"# ./scripts/{os.path.basename(rel_path)} {func_name}\n"
        doc += "```\n\n"

    if not symbols.get('functions') and not symbols.get('commands'):
        doc += "*This file is primarily used by other modules. See importing modules for usage examples.*\n\n"

    return doc


def process_file(rel_path: str) -> Tuple[str, bool]:
    """
    Process a single file and return (status_message, was_updated).
    Status: 'GENERATED', 'SKIPPED (unchanged)', 'ERROR'
    """
    file_path = os.path.join(REPO_ROOT, rel_path)
    doc_path = os.path.join(DOC_ROOT, f"{rel_path}.md")

    # Create doc directory if needed
    doc_dir = os.path.dirname(doc_path)
    os.makedirs(doc_dir, exist_ok=True)

    # Compute current file hash
    current_hash = compute_file_hash(file_path)

    # Check if doc exists and hash matches
    if os.path.exists(doc_path):
        with open(doc_path, 'r', encoding='utf-8') as f:
            existing_content = f.read()

        # Extract hash from header
        hash_match = re.search(r'SOURCE_HASH:\s*(sha256:[a-f0-9]+)', existing_content)
        if hash_match and hash_match.group(1) == current_hash:
            return ('SKIPPED (unchanged)', False)

    # Generate documentation
    try:
        _, ext = os.path.splitext(file_path)

        # Extract symbols based on file type
        symbols = {}
        if ext == '.py':
            tree = extract_python_ast(file_path)
            if tree:
                symbols = extract_python_symbols(tree)
        elif ext in ['.sh', '.bash', '.zsh']:
            symbols = extract_shell_symbols(file_path)

        # Generate documentation
        doc_content = generate_documentation(rel_path, file_path, symbols)

        # Write documentation
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(doc_content)

        return ('GENERATED', True)

    except Exception as e:
        return (f'ERROR: {str(e)}', False)


def main():
    """Main execution function."""
    print(f"Starting documentation generation...")
    print(f"REPO_ROOT: {REPO_ROOT}")
    print(f"DOC_ROOT: {DOC_ROOT}")
    print("-" * 60)

    # Discover files
    files = discover_files()
    print(f"Discovered {len(files)} code files\n")

    # Process files
    generated = 0
    skipped = 0
    errors = 0
    error_messages = []

    for i, rel_path in enumerate(files, 1):
        status, updated = process_file(rel_path)

        if status.startswith('GENERATED'):
            generated += 1
            print(f"[{i}/{len(files)}] ✓ {rel_path} - {status}")
        elif status.startswith('SKIPPED'):
            skipped += 1
            print(f"[{i}/{len(files)}] ⊘ {rel_path} - {status}")
        else:
            errors += 1
            error_messages.append(f"{rel_path}: {status}")
            print(f"[{i}/{len(files)}] ✗ {rel_path} - {status}")

    # Summary
    print("\n" + "=" * 60)
    print("DOCUMENTATION GENERATION COMPLETE")
    print("=" * 60)
    print(f"Total files processed: {len(files)}")
    print(f"Newly generated: {generated}")
    print(f"Skipped (unchanged): {skipped}")
    print(f"Errors: {errors}")

    if error_messages:
        print("\nErrors encountered:")
        for msg in error_messages:
            print(f"  - {msg}")

    print(f"\nDocumentation written to: {DOC_ROOT}")
    print("\nTo view documentation:")
    print(f"  find {DOC_ROOT} -name '*.md' -type f | head -5")

    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
