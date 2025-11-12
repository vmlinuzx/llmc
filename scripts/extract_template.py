#!/usr/bin/env python3
"""
LLM Commander Template Extractor

This script extracts the core context magic from LLM Commander into a clean template
structure, organizing components according to the living template design.

Usage:
    python scripts/extract_template.py [--output-dir DIR] [--components COMP1,COMP2] [--full]
    
Components:
    - rag: RAG system (tools/rag and scripts/rag)
    - scripts: Core orchestration scripts
    - config: Configuration files
    - docs: Core documentation
    - utilities: Core utilities and integration components
    - adapters: LLM integration templates
    - node: Contract loading system
    - examples: Usage examples
    - prompts: Agent prompts
    - llmc_exec: Execution framework
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Set, Optional
import tempfile
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('template_extraction.log')
    ]
)
logger = logging.getLogger(__name__)


class TemplateExtractor:
    """Extracts and organizes LLM Commander components into template structure."""
    
    def __init__(self, source_root: Path, output_dir: Path):
        self.source_root = source_root
        self.output_dir = output_dir
        self.extracted_files: List[str] = []
        self.skipped_files: List[str] = []
        self.errors: List[str] = []
        
        # Component definitions as per template_extraction_plan.md
        self.component_files = {
            'rag': [
                'user_input_files/tools/rag/cli.py',
                'user_input_files/tools/rag/config.py',
                'user_input_files/tools/rag/indexer.py',
                'user_input_files/tools/rag/search.py',
                'user_input_files/tools/rag/utils.py',
                'user_input_files/tools/rag/analytics.py',
                'user_input_files/tools/rag/benchmark.py',
                'user_input_files/scripts/rag/ast_chunker.py',
                'user_input_files/scripts/rag/index_workspace.py',
                'user_input_files/scripts/rag/query_context.py',
                'user_input_files/scripts/rag/rag_server.py',
                'user_input_files/scripts/rag/watch_workspace.py',
            ],
            'scripts': [
                'user_input_files/scripts/bootstrap.py',
                'user_input_files/scripts/llm_gateway.js',
                'user_input_files/scripts/llm_gateway.sh',
                'user_input_files/scripts/claude_wrap.sh',
                'user_input_files/scripts/codex_wrap.sh',
                'user_input_files/scripts/gemini_wrap.sh',
                'user_input_files/scripts/contracts_build.py',
                'user_input_files/scripts/contracts_render.py',
                'user_input_files/scripts/contracts_validate.py',
            ],
            'config': [
                'user_input_files/llmc.toml',
                'user_input_files/config/deep_research_services.json',
                'user_input_files/config/llmc_concurrency.env.example',
                'user_input_files/profiles/claude.yml',
                'user_input_files/profiles/codex.yml',
                'user_input_files/profiles/gemini.yml',
                'user_input_files/presets/enrich_7b_ollama.yaml',
                'user_input_files/router/policy.json',
            ],
            'docs': [
                'user_input_files/AGENTS.md',
                'user_input_files/CONTRACTS.md',
                'user_input_files/DOCS/Key_Directory_Structure.md',
                'user_input_files/DOCS/Local_Development_Tooling.md',
                'user_input_files/DOCS/Claude_Orchestration_Playbook.md',
                'user_input_files/DOCS/ROUTING.md',
                'user_input_files/DOCS/System_Specs.md',
                'user_input_files/DOCS/TESTING_PROTOCOL.md',
            ],
            'utilities': [
                'user_input_files/tools/cache',
                'user_input_files/tools/diagnostics/health_check.py',
                'user_input_files/llmc_exec',
            ],
            'adapters': [
                'user_input_files/adapters/claude.tools.tmpl',
                'user_input_files/adapters/codex.tools.tmpl',
                'user_input_files/adapters/gemini.tools.tmpl',
            ],
            'node': [
                'user_input_files/node/contracts_loader.js',
            ],
            'examples': [
                'user_input_files/examples/llmc/changeset_example.json',
            ],
            'prompts': [
                'user_input_files/prompts/porting_agent.md',
            ]
        }
        
        # Files to exclude (template builder specific, legacy, etc.)
        self.exclude_patterns = {
            'template',
            'apps/template-builder',
            'apps/web',
            'research',
            'ops',
            'logs',
            'user_input_files/scripts/llmc_lock.py',
            'user_input_files/scripts/build_kit.py',
            'user_input_files/scripts/pdf_to_md.sh',
            'user_input_files/scripts/increase_capacity.sh',
            'user_input_files/scripts/gateway_cost_rollup.js',
            'user_input_files/scripts/metrics_sinks',
        }
    
    def extract_all_components(self):
        """Extract all core components to template structure."""
        logger.info("Starting full template extraction...")
        
        # Create base template structure
        self._create_template_structure()
        
        # Extract each component
        for component in self.component_files:
            logger.info(f"Extracting {component} component...")
            self._extract_component(component)
        
        # Process configuration files
        self._process_configurations()
        
        # Create additional template files
        self._create_template_files()
        
        # Generate summary report
        self._generate_summary()
        
        logger.info(f"Template extraction completed. Output: {self.output_dir}")
    
    def extract_specific_components(self, components: List[str]):
        """Extract only specified components."""
        logger.info(f"Extracting specific components: {', '.join(components)}")
        
        # Validate components
        valid_components = [c for c in components if c in self.component_files]
        invalid_components = [c for c in components if c not in self.component_files]
        
        if invalid_components:
            logger.warning(f"Invalid components: {', '.join(invalid_components)}")
        
        if not valid_components:
            logger.error("No valid components specified")
            return False
        
        # Create base template structure
        self._create_template_structure()
        
        # Extract each valid component
        for component in valid_components:
            logger.info(f"Extracting {component} component...")
            self._extract_component(component)
        
        # Process configuration files if included
        if 'config' in valid_components:
            self._process_configurations()
        
        # Create additional template files
        self._create_template_files()
        
        # Generate summary report
        self._generate_summary()
        
        logger.info(f"Template extraction completed. Output: {self.output_dir}")
        return True
    
    def _create_template_structure(self):
        """Create the template directory structure."""
        template_dirs = [
            'llmc_template',
            'llmc_template/config',
            'llmc_template/config/profiles',
            'llmc_template/config/presets',
            'llmc_template/scripts',
            'llmc_template/tools',
            'llmc_template/tools/rag',
            'llmc_template/tools/cache',
            'llmc_template/tools/diagnostics',
            'llmc_template/docs',
            'llmc_template/adapters',
            'llmc_template/node',
            'llmc_template/examples',
            'llmc_template/prompts',
            'llmc_template/llmc_exec',
        ]
        
        for dir_path in template_dirs:
            full_path = self.output_dir / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {full_path}")
    
    def _extract_component(self, component: str):
        """Extract a specific component."""
        files_to_extract = self.component_files[component]
        
        for file_path in files_to_extract:
            try:
                self._extract_file_or_directory(file_path, component)
            except Exception as e:
                error_msg = f"Error extracting {file_path}: {str(e)}"
                self.errors.append(error_msg)
                logger.error(error_msg)
    
    def _extract_file_or_directory(self, source_path: str, component: str):
        """Extract a file or directory to the template."""
        source_full = self.source_root / source_path
        
        # Check if path should be excluded
        if self._should_exclude(source_full):
            self.skipped_files.append(source_path)
            logger.debug(f"Skipped excluded path: {source_path}")
            return
        
        if source_full.is_file():
            self._copy_file(source_full, source_path, component)
        elif source_full.is_dir():
            self._copy_directory(source_full, source_path, component)
        else:
            warning_msg = f"Source path not found: {source_path}"
            logger.warning(warning_msg)
            self.skipped_files.append(source_path)
    
    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded."""
        path_str = str(path.relative_to(self.source_root))
        
        for pattern in self.exclude_patterns:
            if pattern in path_str:
                return True
        return False
    
    def _copy_file(self, source_file: Path, source_path: str, component: str):
        """Copy a single file to the template with path adjustment."""
        # Determine target path based on component
        target_path = self._get_target_path(source_path, component)
        target_file = self.output_dir / target_path
        
        # Adjust file content for new paths
        content = source_file.read_text()
        adjusted_content = self._adjust_paths(content, source_path, target_path)
        
        # Ensure target directory exists
        target_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write adjusted content
        target_file.write_text(adjusted_content)
        
        self.extracted_files.append(target_path)
        logger.debug(f"Extracted file: {source_path} -> {target_path}")
    
    def _copy_directory(self, source_dir: Path, source_path: str, component: str):
        """Copy a directory and its contents."""
        target_path = self._get_target_path(source_path, component)
        target_dir = self.output_dir / target_path
        
        # Copy directory
        if target_dir.exists():
            shutil.rmtree(target_dir)
        
        shutil.copytree(source_dir, target_dir)
        
        # Adjust paths in all files within the directory
        for file_path in target_dir.rglob('*'):
            if file_path.is_file():
                content = file_path.read_text()
                adjusted_content = self._adjust_paths(content, source_path, target_path)
                file_path.write_text(adjusted_content)
        
        self.extracted_files.append(target_path)
        logger.debug(f"Extracted directory: {source_path} -> {target_path}")
    
    def _get_target_path(self, source_path: str, component: str) -> str:
        """Get the target path in the template structure."""
        path_mappings = {
            'rag': {
                'user_input_files/tools/rag/': 'tools/rag/',
                'user_input_files/scripts/rag/': 'scripts/rag/',
            },
            'scripts': {
                'user_input_files/scripts/': 'scripts/',
            },
            'config': {
                'user_input_files/llmc.toml': 'config/default.toml',
                'user_input_files/config/': 'config/',
                'user_input_files/profiles/': 'config/profiles/',
                'user_input_files/presets/': 'config/presets/',
                'user_input_files/router/': 'config/router/',
            },
            'docs': {
                'user_input_files/': 'docs/',
                'user_input_files/DOCS/': 'docs/',
            },
            'utilities': {
                'user_input_files/tools/cache/': 'tools/cache/',
                'user_input_files/tools/diagnostics/': 'tools/diagnostics/',
                'user_input_files/llmc_exec/': 'llmc_exec/',
            },
            'adapters': {
                'user_input_files/adapters/': 'adapters/',
            },
            'node': {
                'user_input_files/node/': 'node/',
            },
            'examples': {
                'user_input_files/examples/': 'examples/',
            },
            'prompts': {
                'user_input_files/prompts/': 'prompts/',
            }
        }
        
        component_mappings = path_mappings.get(component, {})
        for source_prefix, target_prefix in component_mappings.items():
            if source_path.startswith(source_prefix):
                return source_path.replace(source_prefix, target_prefix, 1)
        
        return source_path
    
    def _adjust_paths(self, content: str, source_path: str, target_path: str) -> str:
        """Adjust paths in file content to work from llmc/ root."""
        # Common path adjustments for scripts
        content = content.replace('tools/rag', 'llmc_template/tools/rag')
        content = content.replace('scripts/rag', 'llmc_template/scripts/rag')
        content = content.replace('config/', 'llmc_template/config/')
        content = content.replace('profiles/', 'llmc_template/config/profiles/')
        content = content.replace('router/', 'llmc_template/config/router/')
        
        # Adjust imports and references
        if content.strip().startswith('#!/bin/bash') or content.strip().startswith('#!/usr/bin/env'):
            # Shell script path adjustments
            content = self._adjust_shell_paths(content)
        elif 'import' in content and '.py' in content:
            # Python file path adjustments
            content = self._adjust_python_paths(content)
        
        return content
    
    def _adjust_shell_paths(self, content: str) -> str:
        """Adjust paths in shell scripts."""
        # Common path patterns to adjust
        adjustments = [
            ('tools/rag', 'llmc_template/tools/rag'),
            ('scripts/rag', 'llmc_template/scripts/rag'),
            ('tools/', 'llmc_template/tools/'),
            ('scripts/', 'llmc_template/scripts/'),
        ]
        
        for old_path, new_path in adjustments:
            # Adjust path references in script logic
            content = content.replace(f'$SCRIPT_DIR/../{old_path}', f'$LLMC_ROOT/{new_path}')
            content = content.replace(f'"../{old_path}"', f'"../{new_path}"')
        
        return content
    
    def _adjust_python_paths(self, content: str) -> str:
        """Adjust paths in Python files."""
        # Add path adjustment for template structure
        path_adjustment = """
import sys
from pathlib import Path

# Add llmc template paths for template usage
TEMPLATE_ROOT = Path(__file__).parent.parent / "llmc_template"
sys.path.append(str(TEMPLATE_ROOT / "tools"))
"""
        
        if 'from pathlib import Path' in content:
            return content
        
        return path_adjustment + content
    
    def _process_configurations(self):
        """Process configuration files for defaults vs local overrides."""
        logger.info("Processing configuration files...")
        
        # Create local example config
        local_example = self.output_dir / 'llmc_template/config/local.example.toml'
        if local_example.exists():
            # Read existing config
            default_config = self.output_dir / 'llmc_template/config/default.toml'
            if default_config.exists():
                content = default_config.read_text()
                
                # Create local example with comments
                example_content = f"""# Local Configuration Example
# Copy this file to 'local.toml' and modify as needed
# Values in local.toml override defaults

{content}
"""
                local_example.write_text(example_content)
        
        # Create .gitignore for template
        gitignore_content = """# Local configuration
config/local.toml

# Runtime data
.llmc/
.llmc/index/
.llmc/cache/
.llmc/logs/

# Template build artifacts
llmc_template/
*.egg-info/
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
"""
        
        gitignore_path = self.output_dir / 'llmc_template/.gitignore'
        gitignore_path.write_text(gitignore_content)
        
        logger.debug("Configuration files processed")
    
    def _create_template_files(self):
        """Create additional template files."""
        logger.info("Creating template files...")
        
        # Create main README
        readme_content = """# LLM Commander Template

This is the LLM Commander template - a clean extraction of the core context management magic
for LLM orchestration.

## Quick Start

1. **Bootstrap the template:**
   ```bash
   cd llmc_template
   python scripts/bootstrap.py
   ```

2. **Configure for your environment:**
   ```bash
   cp config/local.example.toml config/local.toml
   # Edit config/local.toml as needed
   ```

3. **Start using LLM Commander:**
   ```bash
   # Use Claude
   ./scripts/claude_wrap.sh "Your task here"
   
   # Use local models
   ./scripts/codex_wrap.sh "Your task here"
   
   # Use Gemini
   ./scripts/gemini_wrap.sh "Your task here"
   ```

## Template Structure

- `config/` - Configuration files (defaults and local overrides)
- `scripts/` - Core orchestration scripts
- `tools/rag/` - RAG (Retrieval-Augmented Generation) system
- `docs/` - Core documentation and operational guidelines
- `adapters/` - LLM integration templates
- `examples/` - Usage examples and patterns

## Core Features

- **RAG-powered context retrieval** - Local semantic search over codebases
- **Multi-provider LLM routing** - Seamless switching between providers
- **Contract-based context management** - Structured context requirements
- **Profile-driven configuration** - Adaptable settings for different models
- **Agent charter system** - Clear roles and operational guidelines

## Configuration

The template uses a layered configuration approach:

1. `config/default.toml` - System defaults (git-tracked)
2. `config/local.toml` - User overrides (git-ignored)
3. Environment variables - Runtime overrides

Copy `config/local.example.toml` to `config/local.toml` to customize.

## RAG System

The template includes a complete RAG system for local codebase understanding:

```bash
# Index your codebase
./scripts/rag/rag_refresh.sh

# Search context
./tools/rag/cli.py search "your query"
```

## Support

See the documentation in the `docs/` directory for detailed usage information.
"""
        
        readme_path = self.output_dir / 'llmc_template/README.md'
        readme_path.write_text(readme_content)
        
        # Create bootstrap script
        bootstrap_content = """#!/usr/bin/env python3
\"\"\"
Bootstrap script for LLM Commander template.
Sets up the environment and creates necessary directories.
\"\"\"

import os
import sys
from pathlib import Path

def main():
    print("🤖 LLM Commander Template Bootstrap")
    print("=" * 40)
    
    # Create runtime directories
    runtime_dirs = [
        ".llmc",
        ".llmc/index", 
        ".llmc/cache",
        ".llmc/logs"
    ]
    
    for dir_path in runtime_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created {dir_path}/")
    
    # Copy local config if it doesn't exist
    local_config = Path("config/local.toml")
    if not local_config.exists():
        example_config = Path("config/local.example.toml")
        if example_config.exists():
            shutil.copy2(example_config, local_config)
            print("✓ Created config/local.toml from example")
        else:
            print("⚠ No local.example.toml found")
    
    # Validate configuration
    print("\\n📋 Validating configuration...")
    try:
        import toml
        with open("config/default.toml") as f:
            config = toml.load(f)
        print("✓ Default configuration is valid")
    except ImportError:
        print("⚠ toml not installed - run: pip install toml")
    except Exception as e:
        print(f"⚠ Configuration error: {e}")
    
    print("\\n🎉 Bootstrap completed!")
    print("\\nNext steps:")
    print("1. Edit config/local.toml if needed")
    print("2. Run ./scripts/rag_refresh.sh to index your codebase")
    print("3. Start using LLM Commander!")

if __name__ == "__main__":
    import shutil
    main()
"""
        
        bootstrap_path = self.output_dir / 'llmc_template/scripts/bootstrap_template.py'
        bootstrap_path.write_text(bootstrap_content)
        bootstrap_path.chmod(0o755)
        
        logger.debug("Template files created")
    
    def _generate_summary(self):
        """Generate extraction summary report."""
        summary = {
            'extraction_date': datetime.now().isoformat(),
            'source_root': str(self.source_root),
            'output_dir': str(self.output_dir),
            'extracted_files': self.extracted_files,
            'skipped_files': self.skipped_files,
            'errors': self.errors,
            'statistics': {
                'total_extracted': len(self.extracted_files),
                'total_skipped': len(self.skipped_files),
                'total_errors': len(self.errors)
            }
        }
        
        # Write summary report
        summary_file = self.output_dir / 'extraction_summary.json'
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Print summary
        print(f"\n{'='*50}")
        print("TEMPLATE EXTRACTION SUMMARY")
        print(f"{'='*50}")
        print(f"Extracted files: {len(self.extracted_files)}")
        print(f"Skipped files: {len(self.skipped_files)}")
        print(f"Errors: {len(self.errors)}")
        print(f"Output directory: {self.output_dir}")
        
        if self.errors:
            print(f"\nErrors encountered:")
            for error in self.errors:
                print(f"  - {error}")
        
        print(f"\nSummary saved to: {summary_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Extract LLM Commander template')
    parser.add_argument(
        '--output-dir', 
        type=Path, 
        default=Path('.'),
        help='Output directory for template (default: current directory)'
    )
    parser.add_argument(
        '--components',
        type=str,
        help='Comma-separated list of components to extract (default: all)'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Extract full template (same as --components=all)'
    )
    
    args = parser.parse_args()
    
    # Determine source root
    source_root = Path(__file__).parent.parent
    
    # Create output directory
    output_dir = args.output_dir / 'llmc_template'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize extractor
    extractor = TemplateExtractor(source_root, output_dir)
    
    # Determine what to extract
    if args.full or (not args.components):
        # Extract all components
        extractor.extract_all_components()
    else:
        # Extract specific components
        components = [c.strip() for c in args.components.split(',')]
        success = extractor.extract_specific_components(components)
        if not success:
            sys.exit(1)
    
    print(f"\n✨ Template extraction complete!")
    print(f"📁 Output: {output_dir}")
    print(f"📖 See {output_dir}/README.md for usage instructions")


if __name__ == '__main__':
    main()