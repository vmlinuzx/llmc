#!/usr/bin/env python3
"""
LLMC Configuration CLI Tool

Command-line interface for managing LLMC configuration.
Provides easy access to configuration validation, migration, and management.
"""

import argparse
import sys
from pathlib import Path
import json
import toml

try:
    from .config import Config, load_config
    from .validate import ConfigValidator, ConfigMigrator
except ImportError:
    from config import Config, load_config
    from validate import ConfigValidator, ConfigMigrator


def cmd_show(args):
    """Show current configuration."""
    try:
        config = load_config(Path(args.config_dir) if args.config_dir else None)
        
        if args.key:
            # Show specific key
            value = config.get(args.key)
            if value is None:
                print(f"Key '{args.key}' not found", file=sys.stderr)
                return 1
            
            if args.format == 'json':
                print(json.dumps({args.key: value}, indent=2))
            else:
                print(value)
        else:
            # Show all configuration
            if args.format == 'json':
                print(json.dumps(config.to_dict(), indent=2))
            elif args.format == 'toml':
                print(toml.dumps(config.to_dict()))
            else:
                # Human-readable format
                print("LLMC Configuration:")
                print("=" * 50)
                for section in config.keys():
                    print(f"\n[{section}]")
                    section_config = config.section(section)
                    for key in section_config.keys():
                        value = section_config.get(key)
                        if isinstance(value, bool):
                            value_str = "true" if value else "false"
                        elif isinstance(value, dict):
                            value_str = "{...}"
                        elif isinstance(value, list):
                            value_str = str(value)
                        else:
                            value_str = str(value)
                        print(f"  {key} = {value_str}")
        
        return 0
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1


def cmd_validate(args):
    """Validate configuration."""
    validator = ConfigValidator()
    success = True
    
    if args.config_file:
        # Validate specific file
        if not validator.validate_file(Path(args.config_file)):
            success = False
    else:
        # Validate current configuration
        try:
            config = load_config(Path(args.config_dir) if args.config_dir else None)
            if not validator.validate_config_object(config):
                success = False
        except Exception as e:
            print(f"Error loading configuration: {e}", file=sys.stderr)
            return 1
    
    # Print results
    summary = validator.get_validation_summary()
    print(summary)
    
    if args.verbose and (validator.errors or validator.warnings):
        print("\nDetailed analysis:")
        if validator.errors:
            print("Errors:")
            for error in validator.errors:
                print(f"  ❌ {error}")
        
        if validator.warnings:
            print("Warnings:")
            for warning in validator.warnings:
                print(f"  ⚠️ {warning}")
    
    return 0 if success else 1


def cmd_migrate(args):
    """Migrate from old configuration format."""
    old_config_path = Path(args.old_config)
    output_dir = Path(args.output_dir) if args.output_dir else Path("config")
    
    print(f"Migrating {old_config_path} to {output_dir}")
    
    if ConfigMigrator.migrate_from_old_config(old_config_path, output_dir):
        print("Migration completed successfully!")
        print(f"Next steps:")
        print(f"  1. Review the generated files in {output_dir}")
        print(f"  2. Copy {output_dir}/local.example.toml to {output_dir}/local.toml")
        print(f"  3. Customize {output_dir}/local.toml for your needs")
        return 0
    else:
        print("Migration failed!", file=sys.stderr)
        return 1


def cmd_set(args):
    """Set a configuration value."""
    try:
        config = load_config(Path(args.config_dir) if args.config_dir else None)
        config.set(args.key, args.value)
        
        # If in write mode, save to local.toml
        if args.write:
            local_config_path = Path(args.config_dir or "config") / "local.toml"
            local_config_path.parent.mkdir(exist_ok=True)
            
            # Load existing local config or create new
            if local_config_path.exists():
                with open(local_config_path, 'r') as f:
                    local_config = toml.load(f)
            else:
                local_config = {}
            
            # Set the value in local config
            keys = args.key.split('.')
            current = local_config
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            current[keys[-1]] = args.value
            
            # Write back to file
            with open(local_config_path, 'w') as f:
                toml.dump(local_config, f)
            
            print(f"Updated {local_config_path}")
        else:
            print(f"Set {args.key} = {args.value} (in-memory only)")
            print("Use --write to save to local.toml")
        
        return 0
    except Exception as e:
        print(f"Error setting configuration: {e}", file=sys.stderr)
        return 1


def cmd_get(args):
    """Get a configuration value."""
    try:
        config = load_config(Path(args.config_dir) if args.config_dir else None)
        value = config.get(args.key)
        
        if value is None:
            print(f"Key '{args.key}' not found", file=sys.stderr)
            return 1
        
        if args.format == 'json':
            print(json.dumps(value))
        else:
            print(value)
        
        return 0
    except Exception as e:
        print(f"Error getting configuration: {e}", file=sys.stderr)
        return 1


def cmd_init(args):
    """Initialize configuration for a project."""
    config_dir = Path(args.config_dir) if args.config_dir else Path("config")
    
    print(f"Initializing LLMC configuration in {config_dir}")
    
    # Create config directory
    config_dir.mkdir(exist_ok=True)
    profiles_dir = config_dir / "profiles"
    profiles_dir.mkdir(exist_ok=True)
    
    # Copy default and example files if they don't exist
    default_config = config_dir / "default.toml"
    example_config = config_dir / "local.example.toml"
    
    if not default_config.exists():
        # Create a minimal default config
        default_data = {
            'embeddings': {
                'preset': 'e5',
                'model': 'intfloat/e5-base-v2'
            },
            'storage': {
                'index_path': '.llmc/index/index_v2.db',
                'cache_path': '.llmc/cache'
            },
            'logging': {
                'level': 'INFO',
                'file': '.llmc/logs/llmc.log',
                'console_output': True
            },
            'semantic_cache': {
                'enabled': True,
                'min_score': 0.7
            },
            'providers': {
                'default': 'claude',
                'claude': {
                    'enabled': True,
                    'api_key_env': 'ANTHROPIC_API_KEY',
                    'model': 'claude-sonnet-4-20250514'
                },
                'ollama': {
                    'enabled': True,
                    'base_url': 'http://localhost:11434',
                    'model': 'qwen2.5:14b'
                }
            }
        }
        
        with open(default_config, 'w') as f:
            toml.dump(default_data, f)
        print(f"Created {default_config}")
    
    if not example_config.exists():
        # Create a simple example config
        example_data = {
            '#': 'LLMC Local Configuration Example',
            '#': 'Copy this file to "local.toml" and modify as needed',
            '#': 'This file is git-ignored by default',
            'providers': {
                'default': 'ollama',  # Uncomment to use local Ollama by default
            }
        }
        
        with open(example_config, 'w') as f:
            toml.dump(example_data, f)
        print(f"Created {example_config}")
    
    # Create .gitignore entry
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        with open(gitignore_path, 'r') as f:
            content = f.read()
        if 'config/local.toml' not in content:
            with open(gitignore_path, 'a') as f:
                f.write('\n# LLMC local configuration\nconfig/local.toml\n')
            print("Added config/local.toml to .gitignore")
    
    # Create .llmc directory structure
    llmc_dir = Path('.llmc')
    (llmc_dir / 'index').mkdir(parents=True, exist_ok=True)
    (llmc_dir / 'cache').mkdir(parents=True, exist_ok=True)
    (llmc_dir / 'logs').mkdir(parents=True, exist_ok=True)
    print(f"Created .llmc directory structure")
    
    print("\nConfiguration initialized successfully!")
    print("Next steps:")
    print("  1. Copy config/local.example.toml to config/local.toml")
    print("  2. Customize config/local.toml for your needs")
    print("  3. Run: python -m config.validate --validate")
    
    return 0


def cmd_profiles(args):
    """List available provider profiles."""
    profiles_dir = Path(args.config_dir or "config") / "profiles"
    
    if not profiles_dir.exists():
        print("No profiles directory found", file=sys.stderr)
        return 1
    
    if args.list:
        # List all profiles
        profiles = list(profiles_dir.glob("*.yml")) + list(profiles_dir.glob("*.yaml"))
        if not profiles:
            print("No profiles found", file=sys.stderr)
            return 1
        
        for profile_file in sorted(profiles):
            name = profile_file.stem
            print(f"  {name}")
        return 0
    
    elif args.name:
        # Show specific profile
        profile_file = profiles_dir / f"{args.name}.yml"
        if not profile_file.exists():
            profile_file = profiles_dir / f"{args.name}.yaml"
        
        if not profile_file.exists():
            print(f"Profile '{args.name}' not found", file=sys.stderr)
            return 1
        
        try:
            import yaml
            with open(profile_file, 'r') as f:
                profile = yaml.safe_load(f)
            
            print(f"Profile: {profile.get('name', args.name)}")
            print(f"Display: {profile.get('display_name', 'N/A')}")
            print(f"Description: {profile.get('description', 'N/A')}")
            
            if 'model' in profile:
                model_info = profile['model']
                if isinstance(model_info, dict):
                    print(f"Model: {model_info.get('name', 'N/A')}")
                else:
                    print(f"Model: {model_info}")
            
            if 'use_cases' in profile:
                print("Use cases:")
                for use_case in profile['use_cases']:
                    print(f"  - {use_case}")
            
            return 0
        except Exception as e:
            print(f"Error loading profile: {e}", file=sys.stderr)
            return 1
    
    else:
        print("Usage: llmc-config profiles --list | --name <name>", file=sys.stderr)
        return 1


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="LLMC Configuration Manager",
        prog="llmc-config"
    )
    parser.add_argument("--config-dir", help="Configuration directory path")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Show command
    show_parser = subparsers.add_parser("show", help="Show configuration")
    show_parser.add_argument("key", nargs="?", help="Specific key to show")
    show_parser.add_argument("--format", choices=['plain', 'json', 'toml'], default='plain', help="Output format")
    show_parser.set_defaults(func=cmd_show)
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration")
    validate_parser.add_argument("--config-file", help="Specific config file to validate")
    validate_parser.add_argument("--verbose", action="store_true", help="Verbose output")
    validate_parser.set_defaults(func=cmd_validate)
    
    # Migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Migrate from old config")
    migrate_parser.add_argument("old_config", help="Path to old configuration file")
    migrate_parser.add_argument("--output-dir", help="Output directory for new config")
    migrate_parser.set_defaults(func=cmd_migrate)
    
    # Set command
    set_parser = subparsers.add_parser("set", help="Set configuration value")
    set_parser.add_argument("key", help="Configuration key (e.g., 'providers.default')")
    set_parser.add_argument("value", help="Value to set")
    set_parser.add_argument("--write", action="store_true", help="Write to local.toml")
    set_parser.set_defaults(func=cmd_set)
    
    # Get command
    get_parser = subparsers.add_parser("get", help="Get configuration value")
    get_parser.add_argument("key", help="Configuration key")
    get_parser.add_argument("--format", choices=['plain', 'json'], default='plain', help="Output format")
    get_parser.set_defaults(func=cmd_get)
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize configuration")
    init_parser.set_defaults(func=cmd_init)
    
    # Profiles command
    profiles_parser = subparsers.add_parser("profiles", help="Manage provider profiles")
    group = profiles_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List all profiles")
    group.add_argument("--name", help="Show specific profile")
    profiles_parser.set_defaults(func=cmd_profiles)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute command
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())