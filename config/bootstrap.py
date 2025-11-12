#!/usr/bin/env python3
"""
LLMC Configuration Bootstrap Script

Initializes the LLMC configuration system for a new project.
This script can be run standalone or integrated into existing setup processes.
"""

import sys
import argparse
from pathlib import Path
import shutil
import toml
import os

def create_directory_structure(base_path: Path) -> None:
    """Create the required directory structure."""
    directories = [
        base_path / "config",
        base_path / "config" / "profiles", 
        base_path / ".llmc",
        base_path / ".llmc" / "index",
        base_path / ".llmc" / "cache",
        base_path / ".llmc" / "logs",
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")

def create_default_config(config_path: Path) -> None:
    """Create the default configuration file."""
    default_config = {
        'embeddings': {
            'preset': 'e5',
            'model': 'intfloat/e5-base-v2'
        },
        'storage': {
            'index_path': '.llmc/index/index_v2.db',
            'cache_path': '.llmc/cache'
        },
        'enrichment': {
            'enabled': False,
            'model': 'gpt-4o-mini',
            'batch_size': 50
        },
        'logging': {
            'level': 'INFO',
            'file': '.llmc/logs/llmc.log',
            'console_output': True
        },
        'concurrency': {
            'enabled': False,
            'max_concurrent_tasks': 4,
            'task_timeout': 300
        },
        'semantic_cache': {
            'enabled': True,
            'provider': 'default',
            'min_score': 0.7
        },
        'deep_research': {
            'enabled': False,
            'auto_route_override': False,
            'recommendation_threshold': 0.6
        },
        'providers': {
            'default': 'claude',
            'claude': {
                'enabled': True,
                'api_key_env': 'ANTHROPIC_API_KEY',
                'model': 'claude-sonnet-4-20250514'
            },
            'azure': {
                'enabled': False,
                'endpoint_env': 'AZURE_OPENAI_ENDPOINT',
                'key_env': 'AZURE_OPENAI_KEY',
                'deployment_env': 'AZURE_OPENAI_DEPLOYMENT',
                'api_version': '2024-02-15-preview'
            },
            'gemini': {
                'enabled': False,
                'api_key_env': 'GOOGLE_API_KEY',
                'model': 'gemini-pro'
            },
            'ollama': {
                'enabled': True,
                'base_url': 'http://localhost:11434',
                'model': 'qwen2.5:14b'
            },
            'minimax': {
                'enabled': False,
                'base_url_env': 'MINIMAX_BASE_URL',
                'api_key_env': 'MINIMAXKEY2',
                'model_env': 'MINIMAX_MODEL'
            }
        },
        'rag': {
            'enabled': True,
            'auto_index': True,
            'reindex_on_change': True,
            'min_score': 0.4,
            'min_confidence': 0.6,
            'max_results': 10
        },
        'security': {
            'dangerously_skip_permissions': False,
            'yolo_mode': False,
            'require_confirmation': True
        },
        'templates': {
            'copy_on_first_use': True,
            'backup_existing': True,
            'templates_dir': 'templates'
        },
        'performance': {
            'cache_ttl': 3600,
            'max_memory_usage': '1GB',
            'gc_frequency': 100
        },
        'development': {
            'debug': False,
            'trace_logging': False,
            'log_sql': False,
            'profile_queries': False
        },
        'ui': {
            'color_output': True,
            'progress_bars': True,
            'verbose_errors': False,
            'interactive_mode': True
        }
    }
    
    with open(config_path, 'w') as f:
        toml.dump(default_config, f)
    print(f"Created default configuration: {config_path}")

def create_example_config(example_path: Path) -> None:
    """Create the example local configuration file."""
    example_config = {
        '#': 'LLMC Local Configuration Example',
        '#': 'Copy this file to "local.toml" and modify as needed',
        '#': 'This file is git-ignored by default',
        'providers': {
            '# default': 'ollama',  # Uncomment to use local Ollama by default
        }
    }
    
    with open(example_path, 'w') as f:
        toml.dump(example_config, f)
    print(f"Created example configuration: {example_path}")

def update_gitignore(project_path: Path) -> None:
    """Update .gitignore to exclude local configuration."""
    gitignore_path = project_path / ".gitignore"
    local_config_entry = "\n# LLMC local configuration\nconfig/local.toml\n"
    
    if gitignore_path.exists():
        with open(gitignore_path, 'r') as f:
            content = f.read()
        
        if 'config/local.toml' not in content:
            with open(gitignore_path, 'a') as f:
                f.write(local_config_entry)
            print(f"Updated .gitignore to exclude config/local.toml")
    else:
        with open(gitignore_path, 'w') as f:
            f.write(local_config_entry)
        print(f"Created .gitignore with LLMC exclusions")

def copy_examples(examples_dir: Path, config_dir: Path) -> None:
    """Copy example configuration files."""
    examples_configs = examples_dir / "configs"
    if examples_configs.exists():
        target_configs = config_dir / "examples"
        target_configs.mkdir(exist_ok=True)
        
        for example_file in examples_configs.glob("*.toml"):
            target_file = target_configs / example_file.name
            shutil.copy2(example_file, target_file)
            print(f"Copied example: {target_file}")

def check_dependencies() -> bool:
    """Check if required dependencies are available."""
    try:
        import toml
        import yaml
        return True
    except ImportError as e:
        print(f"Error: Missing dependency: {e}")
        print("Please install required dependencies:")
        print("  pip install toml pyyaml")
        return False

def validate_installation(config_path: Path) -> bool:
    """Validate that the installation was successful."""
    try:
        # Check if we can load the configuration
        from config import Config
        config = Config.load(config_path.parent)
        print("✅ Configuration validation successful")
        return True
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        return False

def main():
    """Main bootstrap function."""
    parser = argparse.ArgumentParser(description="Bootstrap LLMC Configuration System")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--config-dir", help="Configuration directory path (defaults to project-root/config)")
    parser.add_argument("--no-gitignore", action="store_true", help="Don't update .gitignore")
    parser.add_argument("--template", choices=['basic_local', 'production', 'cost_optimized', 'development'], 
                       help="Apply a configuration template")
    parser.add_argument("--validate", action="store_true", help="Validate installation after setup")
    parser.add_argument("--examples-dir", default="examples/configs", help="Path to example configurations")
    
    args = parser.parse_args()
    
    # Check dependencies first
    if not check_dependencies():
        return 1
    
    # Set up paths
    project_root = Path(args.project_root).resolve()
    config_dir = Path(args.config_dir).resolve() if args.config_dir else (project_root / "config")
    examples_dir = Path(args.examples_dir).resolve()
    
    print(f"🚀 Bootstrapping LLMC Configuration System")
    print(f"Project root: {project_root}")
    print(f"Config directory: {config_dir}")
    print()
    
    # Create directory structure
    print("📁 Creating directory structure...")
    create_directory_structure(project_root)
    print()
    
    # Create default configuration
    print("⚙️  Creating default configuration...")
    default_config_path = config_dir / "default.toml"
    create_default_config(default_config_path)
    print()
    
    # Create example configuration
    print("📋 Creating example configuration...")
    example_config_path = config_dir / "local.example.toml"
    create_example_config(example_config_path)
    print()
    
    # Update .gitignore
    if not args.no_gitignore:
        print("📝 Updating .gitignore...")
        update_gitignore(project_root)
        print()
    
    # Copy example configurations
    if examples_dir.exists():
        print("📚 Copying example configurations...")
        copy_examples(examples_dir, config_dir)
        print()
    
    # Apply template if specified
    if args.template:
        template_file = examples_dir / f"{args.template}.toml"
        if template_file.exists():
            local_config_path = config_dir / "local.toml"
            print(f"📄 Applying {args.template} template...")
            shutil.copy2(template_file, local_config_path)
            print(f"Applied template: {local_config_path}")
        else:
            print(f"⚠️  Template {args.template} not found at {template_file}")
        print()
    
    # Validate installation
    if args.validate:
        print("🔍 Validating installation...")
        if validate_installation(config_dir):
            print("✅ Bootstrap completed successfully!")
        else:
            print("❌ Bootstrap completed with validation errors")
            return 1
    else:
        print("✅ Bootstrap completed successfully!")
    
    print()
    print("🎯 Next Steps:")
    print("1. Copy example configuration:")
    print(f"   cp {config_dir}/local.example.toml {config_dir}/local.toml")
    print()
    print("2. Customize configuration:")
    print(f"   Edit {config_dir}/local.toml")
    print()
    print("3. Test configuration:")
    print("   python3 -m config.cli validate")
    print()
    print("4. Use LLMC with your configuration:")
    print("   eval \"$(python3 -m config.cli --export-shell)\"")
    print("   ./scripts/claude_wrap.sh 'Hello, world!'")
    print()
    
    if not (config_dir / "local.toml").exists():
        print("📝 Note: Remember to configure your LLM provider API keys in environment variables")
        print("   or edit config/local.toml with your settings.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())