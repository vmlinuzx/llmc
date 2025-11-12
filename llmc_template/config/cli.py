#!/usr/bin/env python3
"""
LLMC Configuration CLI

Command-line interface for managing LLMC configuration with 3-tier hierarchy.
"""

import click
import json
from pathlib import Path
from config import get_config

@click.group()
def cli():
    """LLMC Configuration Management CLI."""
    pass

@cli.command()
@click.argument('key')
@click.option('--default', help='Default value if key not found')
def get(key, default):
    """Get configuration value."""
    config = get_config()
    value = config.get(key, default)
    
    if value is not None:
        click.echo(f"{key} = {value}")
    else:
        click.echo(f"{key} not found", err=True)
        exit(1)

@cli.command()
@click.argument('key')
@click.argument('value')
@click.option('--level', default='local', help='Configuration level (local only)')
def set(key, value, level):
    """Set configuration value."""
    config = get_config()
    
    # Try to convert value to appropriate type
    from config import ConfigManager
    converted_value = ConfigManager()._convert_value(value)
    
    config.set(key, converted_value, level)
    click.echo(f"Set {key} = {converted_value} at {level} level")

@cli.command()
@click.option('--key', help='Show specific key')
@click.option('--format', 'output_format', type=click.Choice(['json', 'toml']), default='json')
def show(key, output_format):
    """Show configuration."""
    config = get_config()
    
    if key:
        data = config.show(key)
    else:
        data = config.show()
    
    if output_format == 'json':
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo("Configuration format not implemented yet", err=True)
        exit(1)

@cli.command()
def validate():
    """Validate configuration."""
    config = get_config()
    validation = config.validate()
    
    if validation['valid']:
        click.echo("✅ Configuration is valid")
    else:
        click.echo("❌ Configuration has issues:")
        for issue in validation['issues']:
            click.echo(f"  - {issue}")
        exit(1)
    
    if validation['warnings']:
        click.echo("⚠️  Warnings:")
        for warning in validation['warnings']:
            click.echo(f"  - {warning}")

@cli.command()
@click.argument('file_path')
def import_config(file_path):
    """Import configuration from TOML file."""
    config = get_config()
    path = Path(file_path)
    
    if not path.exists():
        click.echo(f"File not found: {file_path}", err=True)
        exit(1)
    
    try:
        import toml
        with open(path, 'r') as f:
            import_config = toml.load(f)
        
        # Merge imported config into local
        for key, value in import_config.items():
            config.set(key, value, 'local')
        
        click.echo(f"Imported configuration from {file_path}")
    except Exception as e:
        click.echo(f"Error importing config: {e}", err=True)
        exit(1)

@cli.command()
@click.option('--output', '-o', help='Output file path')
def export_config(output):
    """Export current configuration."""
    config = get_config()
    
    # Get effective configuration
    effective_config = config.get_effective_config()
    
    if output:
        path = Path(output)
        try:
            import toml
            with open(path, 'w') as f:
                toml.dump(effective_config, f)
            click.echo(f"Exported configuration to {output}")
        except Exception as e:
            click.echo(f"Error exporting config: {e}", err=True)
            exit(1)
    else:
        click.echo(json.dumps(effective_config, indent=2))

@cli.command()
def bootstrap():
    """Initialize default configuration files."""
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    config = get_config()
    
    # Create default.toml if it doesn't exist
    default_file = config_dir / "default.toml"
    if not default_file.exists():
        default_content = """# LLMC Default Configuration
# This file contains system defaults and should not be modified

[embeddings]
# Default embedding preset
preset = "e5"

[storage]
# Default storage paths (can be overridden)
index_path = ".llmc/.rag/index_v2.db"

[enrichment]
# Default enrichment settings
enabled = false
model = "gpt-4o-mini"

[llm]
# Default LLM settings
model = "claude-3-sonnet"
temperature = 0.7
max_tokens = 4096

[paths]
# Default paths
project_root = "."
cache_dir = ".cache"
temp_dir = ".tmp"
"""
        with open(default_file, 'w') as f:
            f.write(default_content)
        click.echo(f"Created {default_file}")
    
    # Create local.example.toml if it doesn't exist
    example_file = config_dir / "local.example.toml"
    if not example_file.exists():
        example_content = """# LLMC Local Configuration Example
# Copy this file to local.toml and modify for your project

# Provider API Keys
[providers.claude]
api_key = "your-claude-api-key"

[providers.gemini]
api_key = "your-gemini-api-key"

# LLM Settings
[llm]
model = "claude-3-sonnet"
temperature = 0.7

# Storage Paths (override defaults)
[storage]
index_path = ".llmc/.rag/index_v2.db"

# Enrichment Settings
[enrichment]
enabled = true
model = "gpt-4o-mini"

# Custom Paths
[paths]
project_root = "."
cache_dir = ".cache"
temp_dir = ".tmp"
"""
        with open(example_file, 'w') as f:
            f.write(example_content)
        click.echo(f"Created {example_file}")
    
    click.echo("✅ Configuration bootstrap completed")
    click.echo("Copy local.example.toml to local.toml and customize for your project")

if __name__ == '__main__':
    cli()