#!/usr/bin/env python3
"""
LLMC Template Extractor
Extracts core context management components from LLM Commander
"""

import argparse
import shutil
import os
import sys
from pathlib import Path
import json
from datetime import datetime
from typing import List, Dict, Set

def log(message: str, level: str = "INFO"):
    """Simple logging with timestamps"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    level_prefix = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}
    symbol = level_prefix.get(level, "ℹ️")
    print(f"{symbol} [{timestamp}] {message}")

class TemplateExtractor:
    def __init__(self, output_dir="llmc_template"):
        self.output_dir = Path(output_dir)
        self.src_root = Path.cwd()
        self.extracted_files = []
        self.errors = []
        self.skipped_files = []
        
        # Core components to extract based on the analysis
        self.components = {
            'rag_system': {
                'paths': [
                    'tools/rag',
                    'tools/cache', 
                    'scripts/rag_*.sh',
                    'scripts/rag_*',
                    'scripts/router.py'
                ],
                'description': 'RAG semantic search and indexing'
            },
            'orchestration': {
                'paths': [
                    'scripts/claude_wrap.sh',
                    'scripts/codex_wrap.sh', 
                    'scripts/gemini_wrap.sh',
                    'scripts/llm_gateway.js',
                    'scripts/tool_*.sh',
                    'scripts/integration_gate.sh',
                    'scripts/llmc_*.sh'
                ],
                'description': 'LLM orchestration and routing'
            },
            'configuration': {
                'paths': [
                    'llmc.toml',
                    'config',
                    'presets',
                    'profiles'
                ],
                'description': 'Configuration and profiles'
            },
            'documentation': {
                'paths': [
                    'AGENTS.md',
                    'CLAUDE_AGENTS.md',
                    'CONTRACTS.md',
                    'DOCS/ROUTING.md',
                    'DOCS/SETUP',
                    'DOCS/SCRIPTS/README.md',
                    'DOCS/SCRIPTS/tool_*.sh.md'
                ],
                'description': 'Core documentation and contracts'
            },
            'adapters': {
                'paths': [
                    'adapters',
                    'tools/diagnostics'
                ],
                'description': 'Adapters and diagnostics'
            }
        }
    
    def find_matching_files(self, pattern: str) -> List[Path]:
        """Find files matching glob pattern"""
        matches = []
        if '*' in pattern:
            # Glob pattern
            matches = list(self.src_root.glob(pattern))
        else:
            # Direct path
            path = self.src_root / pattern
            if path.exists():
                matches = [path]
        return [m for m in matches if m.exists()]
    
    def copy_file_or_dir(self, src: Path, dest: Path):
        """Copy file or directory to destination"""
        try:
            if src.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                self.extracted_files.append(str(src.relative_to(self.src_root)))
                log(f"Copied file: {src.relative_to(self.src_root)}")
            elif src.is_dir():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dest, dirs_exist_ok=True)
                self.extracted_files.append(str(src.relative_to(self.src_root)))
                log(f"Copied directory: {src.relative_to(self.src_root)}")
        except Exception as e:
            self.errors.append(f"Failed to copy {src}: {e}")
            log(f"Failed to copy {src.relative_to(self.src_root)}: {e}", "ERROR")
    
    def adjust_file_paths(self, file_path: Path):
        """Adjust hardcoded paths in files to work from llmc/ root"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            original_content = content
            
            # Common path adjustments
            adjustments = [
                # Update script references
                ('../scripts/', './scripts/'),
                ('../tools/', './tools/'),  
                ('../config/', './config/'),
                ('../DOCS/', '../docs/'),
                
                # Update tool paths in scripts
                ('tools/rag/', 'tools/rag/'),
                ('scripts/rag_', 'scripts/rag_'),
                
                # Update RAG paths
                ('.rag/', '.llmc/.rag/'),
                ('.llmc/', '.llmc/'),
            ]
            
            for old_path, new_path in adjustments:
                content = content.replace(old_path, new_path)
            
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                log(f"Adjusted paths in: {file_path.relative_to(self.output_dir)}")
                
        except Exception as e:
            log(f"Could not adjust paths in {file_path}: {e}", "WARNING")
    
    def create_default_config(self):
        """Create default configuration files"""
        config_dir = self.output_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create default.toml from llmc.toml
        if (self.src_root / "llmc.toml").exists():
            shutil.copy2(self.src_root / "llmc.toml", config_dir / "default.toml")
            log("Created default.toml from llmc.toml")
        
        # Create local.example.toml
        example_config = """# LLMC Local Configuration
# Copy this to local.toml and customize for your project

[embeddings]
preset = "e5"

[storage]
index_path = ".llmc/index.db"

[providers]
default = "ollama"
"""
        with open(config_dir / "local.example.toml", 'w') as f:
            f.write(example_config)
        log("Created local.example.toml template")
    
    def create_gitignore(self):
        """Create .gitignore for runtime data"""
        gitignore_content = """
# LLMC Runtime Data (auto-generated)
.llmc/
logs/
.rag/
cache/
"""
        with open(self.output_dir / ".gitignore", 'w') as f:
            f.write(gitignore_content.strip())
        log("Created .gitignore")
    
    def extract_component(self, component_name: str, component_config: Dict):
        """Extract a specific component"""
        log(f"Extracting {component_name}: {component_config['description']}")
        
        for pattern in component_config['paths']:
            matches = self.find_matching_files(pattern)
            
            for match in matches:
                if match.is_file():
                    # For files, create proper directory structure
                    relative_path = match.relative_to(self.src_root)
                    dest_path = self.output_dir / relative_path
                    self.copy_file_or_dir(match, dest_path)
                elif match.is_dir():
                    # For directories, preserve structure
                    relative_path = match.relative_to(self.src_root)
                    dest_path = self.output_dir / relative_path
                    self.copy_file_or_dir(match, dest_path)
    
    def create_porting_script(self):
        """Create a simple porting script for the template"""
        porting_script = """#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def port_to_repo():
    template_dir = Path(__file__).parent
    target_repo = sys.argv[1] if len(sys.argv) > 1 else "."
    
    target_path = Path(target_repo)
    llmc_path = target_path / "llmc"
    
    if llmc_path.exists():
        print(f"llmc/ already exists in {target_repo}")
        return
    
    # Copy template
    import shutil
    shutil.copytree(template_dir, llmc_path)
    print(f"LLMC template deployed to {target_repo}/llmc/")
    
    # Update .gitignore
    gitignore = target_path / ".gitignore"
    if gitignore.exists():
        with open(gitignore, 'a') as f:
            f.write("\\n# LLMC Runtime Data\\n.llmc/\\nlogs/\\n.rag/\\n")
    
    print("Deployment complete!")

if __name__ == "__main__":
    port_to_repo()
"""
        with open(self.output_dir / "deploy.py", 'w') as f:
            f.write(porting_script)
        
        # Make executable
        (self.output_dir / "deploy.py").chmod(0o755)
        log("Created deploy.py script")
    
    def extract(self, components: List[str] = None):
        """Extract template components"""
        log(f"Starting template extraction to: {self.output_dir}")
        
        # Create output directory
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True)
        
        # Extract components
        if components is None:
            components = list(self.components.keys())
        
        for component in components:
            if component not in self.components:
                self.errors.append(f"Unknown component: {component}")
                continue
            
            self.extract_component(component, self.components[component])
        
        # Create supporting files
        self.create_default_config()
        self.create_gitignore()
        self.create_porting_script()
        
        # Adjust paths in all files
        for file_path in self.output_dir.rglob('*'):
            if file_path.is_file():
                self.adjust_file_paths(file_path)
        
        # Generate summary
        self.generate_summary()
    
    def generate_summary(self):
        """Generate extraction summary"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'extracted_files': self.extracted_files,
            'errors': self.errors,
            'skipped_files': self.skipped_files,
            'total_files': len(self.extracted_files)
        }
        
        # Save summary
        with open(self.output_dir / "extraction_summary.json", 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Print summary
        log(f"Extraction complete!", "SUCCESS")
        log(f"Files extracted: {len(self.extracted_files)}")
        log(f"Errors: {len(self.errors)}")
        log(f"Template saved to: {self.output_dir}")
        
        if self.errors:
            log("Errors encountered:", "WARNING")
            for error in self.errors:
                log(f"  - {error}", "WARNING")

def main():
    parser = argparse.ArgumentParser(
        description="Extract LLM Commander template for deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--output", 
        default="llmc_template",
        help="Output directory for template (default: llmc_template)"
    )
    
    parser.add_argument(
        "--components",
        nargs="+",
        choices=['rag_system', 'orchestration', 'configuration', 'documentation', 'adapters'],
        help="Specific components to extract (default: all)"
    )
    
    parser.add_argument(
        "--full",
        action="store_true",
        help="Extract all components (same as no --components)"
    )
    
    args = parser.parse_args()
    
    extractor = TemplateExtractor(args.output)
    components = args.components if args.components else None
    
    try:
        extractor.extract(components)
        return 0
    except KeyboardInterrupt:
        log("Extraction cancelled by user", "WARNING")
        return 1
    except Exception as e:
        log(f"Extraction failed: {e}", "ERROR")
        return 1

if __name__ == "__main__":
    sys.exit(main())