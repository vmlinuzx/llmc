#!/usr/bin/env python3
"""
LLMC Configuration Validation Tool

Validates configuration files for correctness and provides migration helpers.
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
import toml
import yaml
import json

try:
    from .config import Config
except ImportError:
    from config import Config


class ConfigValidator:
    """Validates LLMC configuration files."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
        # Required configuration sections and keys
        self.required_sections = {
            'embeddings': ['preset', 'model'],
            'storage': ['index_path', 'cache_path'],
            'enrichment': ['enabled', 'model', 'batch_size'],
            'logging': ['level', 'file', 'console_output'],
            'semantic_cache': ['enabled', 'min_score'],
            'providers': [],  # Complex structure, validated separately
        }
        
        # Valid values for certain fields
        self.valid_values = {
            'embeddings.preset': ['e5', 'e5-large', 'mini'],
            'logging.level': ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            'enrichment.model': ['gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo'],
            'providers.default': ['claude', 'azure', 'gemini', 'ollama', 'minimax'],
        }
    
    def validate_file(self, config_path: Path) -> bool:
        """Validate a configuration file."""
        if not config_path.exists():
            self.errors.append(f"Configuration file not found: {config_path}")
            return False
        
        try:
            if config_path.suffix == '.toml':
                with open(config_path, 'r') as f:
                    config_data = toml.load(f)
            elif config_path.suffix == '.yml' or config_path.suffix == '.yaml':
                with open(config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
            elif config_path.suffix == '.json':
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
            else:
                self.errors.append(f"Unsupported file format: {config_path.suffix}")
                return False
        except Exception as e:
            self.errors.append(f"Failed to parse {config_path}: {e}")
            return False
        
        return self.validate_structure(config_data, str(config_path))
    
    def validate_config_object(self, config: Config, source: str = "loaded config") -> bool:
        """Validate a Config object."""
        config_data = config.to_dict()
        return self.validate_structure(config_data, source)
    
    def validate_structure(self, config_data: Dict[str, Any], source: str) -> bool:
        """Validate the structure and content of configuration data."""
        is_valid = True
        
        # Check required sections
        for section, required_keys in self.required_sections.items():
            if section not in config_data:
                if self._is_critical_section(section):
                    self.errors.append(f"Missing required section [{section}] in {source}")
                    is_valid = False
                else:
                    self.warnings.append(f"Optional section [{section}] not found in {source}")
                continue
            
            section_data = config_data[section]
            if not isinstance(section_data, dict):
                self.errors.append(f"Section [{section}] must be a dictionary in {source}")
                is_valid = False
                continue
            
            # Check required keys in section
            for key in required_keys:
                if key not in section_data:
                    self.warnings.append(f"Missing key {key} in section [{section}] ({source})")
                else:
                    # Validate the value
                    full_key = f"{section}.{key}"
                    if not self._validate_value(full_key, section_data[key], source):
                        is_valid = False
        
        # Validate providers section structure
        if 'providers' in config_data:
            self._validate_providers(config_data['providers'], source)
        
        # Check for deprecated keys
        self._check_deprecated_keys(config_data, source)
        
        # Validate cross-section dependencies
        self._validate_dependencies(config_data, source)
        
        return len(self.errors) == 0
    
    def _is_critical_section(self, section: str) -> bool:
        """Check if a section is critical for basic functionality."""
        critical_sections = ['embeddings', 'storage', 'logging']
        return section in critical_sections
    
    def _validate_value(self, key: str, value: Any, source: str) -> bool:
        """Validate a configuration value."""
        is_valid = True
        
        # Check valid values
        if key in self.valid_values:
            valid_vals = self.valid_values[key]
            if value not in valid_vals:
                self.errors.append(
                    f"Invalid value '{value}' for {key} in {source}. "
                    f"Valid values: {', '.join(map(str, valid_vals))}"
                )
                is_valid = False
        
        # Type-specific validation
        if key.endswith('.enabled'):
            if not isinstance(value, bool):
                self.errors.append(f"Boolean value required for {key} in {source}")
                is_valid = False
        
        elif key.endswith('.batch_size') or key.endswith('.timeout') or key.endswith('.max_concurrent_tasks'):
            if not isinstance(value, int) or value <= 0:
                self.errors.append(f"Positive integer required for {key} in {source}")
                is_valid = False
        
        elif key.endswith('.min_score') or key.endswith('.temperature') or key.endswith('.top_p'):
            if not isinstance(value, (int, float)) or not (0 <= value <= 1):
                self.errors.append(f"Float between 0-1 required for {key} in {source}")
                is_valid = False
        
        return is_valid
    
    def _validate_providers(self, providers: Dict[str, Any], source: str):
        """Validate providers configuration."""
        if not isinstance(providers, dict):
            self.errors.append(f"Providers section must be a dictionary in {source}")
            return
        
        # Check if default provider is specified and exists
        if 'default' in providers:
            default_provider = providers['default']
            if default_provider not in providers:
                self.warnings.append(
                    f"Default provider '{default_provider}' not found in providers list ({source})"
                )
        
        # Validate each provider
        valid_providers = ['claude', 'azure', 'gemini', 'ollama', 'minimax']
        for provider_name, provider_config in providers.items():
            if provider_name == 'default':
                continue
            
            if provider_name not in valid_providers:
                self.warnings.append(f"Unknown provider '{provider_name}' in {source}")
                continue
            
            if not isinstance(provider_config, dict):
                self.errors.append(f"Provider '{provider_name}' must be a dictionary in {source}")
                continue
            
            # Check if enabled providers have required configuration
            if provider_config.get('enabled', False):
                if provider_name == 'claude':
                    if not provider_config.get('api_key_env') and not provider_config.get('model'):
                        self.warnings.append(f"Claude provider may need api_key_env or model configuration")
                
                elif provider_name == 'azure':
                    required_env_vars = ['endpoint_env', 'key_env', 'deployment_env']
                    missing_vars = [var for var in required_env_vars if not provider_config.get(var)]
                    if missing_vars:
                        self.warnings.append(
                            f"Azure provider missing environment variables: {', '.join(missing_vars)}"
                        )
                
                elif provider_name == 'ollama':
                    if not provider_config.get('base_url'):
                        self.warnings.append("Ollama provider missing base_url")
    
    def _check_deprecated_keys(self, config_data: Dict[str, Any], source: str):
        """Check for deprecated configuration keys."""
        deprecated_keys = {
            'rag.index_path': 'storage.index_path',  # Example deprecation
            'cache.path': 'storage.cache_path',
        }
        
        for old_key, new_key in deprecated_keys.items():
            if self._has_key(config_data, old_key):
                self.warnings.append(
                    f"Deprecated key '{old_key}' found in {source}. "
                    f"Use '{new_key}' instead."
                )
    
    def _has_key(self, data: Dict[str, Any], key_path: str) -> bool:
        """Check if a nested key exists in the configuration data."""
        keys = key_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return False
        return True
    
    def _validate_dependencies(self, config_data: Dict[str, Any], source: str):
        """Validate cross-section dependencies and consistency."""
        # Check that semantic cache is properly configured
        if config_data.get('semantic_cache', {}).get('enabled'):
            # Semantic cache requires embeddings
            if not config_data.get('embeddings'):
                self.errors.append("Semantic cache requires embeddings configuration")
        
        # Check RAG settings
        if config_data.get('rag', {}).get('enabled'):
            # RAG requires storage
            if not config_data.get('storage'):
                self.errors.append("RAG requires storage configuration")
        
        # Check enrichment settings
        if config_data.get('enrichment', {}).get('enabled'):
            # Enrichment should have a model specified
            enrichment_model = config_data.get('enrichment', {}).get('model')
            if not enrichment_model:
                self.errors.append("Enrichment requires a model to be specified")
    
    def get_validation_summary(self) -> str:
        """Get a summary of validation results."""
        summary = []
        
        if self.errors:
            summary.append(f"❌ {len(self.errors)} errors found:")
            for error in self.errors:
                summary.append(f"  - {error}")
        
        if self.warnings:
            summary.append(f"⚠️ {len(self.warnings)} warnings:")
            for warning in self.warnings:
                summary.append(f"  - {warning}")
        
        if not self.errors and not self.warnings:
            summary.append("✅ Configuration is valid")
        elif not self.errors:
            summary.append("✅ Configuration is valid (with warnings)")
        
        return "\n".join(summary)


class ConfigMigrator:
    """Helps migrate between configuration versions."""
    
    @staticmethod
    def migrate_from_old_config(old_config_path: Path, new_config_dir: Path) -> bool:
        """Migrate from an old configuration file to the new 3-tier system."""
        if not old_config_path.exists():
            print(f"Old configuration file not found: {old_config_path}")
            return False
        
        new_config_dir.mkdir(exist_ok=True)
        
        try:
            # Load old configuration
            with open(old_config_path, 'r') as f:
                if old_config_path.suffix == '.toml':
                    old_config = toml.load(f)
                else:
                    print(f"Unsupported format for migration: {old_config_path.suffix}")
                    return False
            
            # Create new default configuration
            new_default = ConfigMigrator._create_default_from_old(old_config)
            default_path = new_config_dir / "default.toml"
            with open(default_path, 'w') as f:
                toml.dump(new_default, f)
            print(f"Created new default config: {default_path}")
            
            # Create example local configuration
            example_path = new_config_dir / "local.example.toml"
            example_config = ConfigMigrator._create_example_from_old(old_config)
            with open(example_path, 'w') as f:
                toml.dump(example_config, f)
            print(f"Created example local config: {example_path}")
            
            return True
            
        except Exception as e:
            print(f"Migration failed: {e}")
            return False
    
    @staticmethod
    def _create_default_from_old(old_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new default configuration based on old format."""
        new_config = {}
        
        # Migrate embeddings
        if 'embeddings' in old_config:
            new_config['embeddings'] = {
                'preset': old_config['embeddings'].get('preset', 'e5'),
                'model': old_config['embeddings'].get('model', 'intfloat/e5-base-v2'),
            }
        
        # Migrate storage
        if 'storage' in old_config:
            new_config['storage'] = {
                'index_path': old_config['storage'].get('index_path', '.llmc/index/index_v2.db'),
                'cache_path': '.llmc/cache',
            }
        
        # Migrate enrichment
        if 'enrichment' in old_config:
            new_config['enrichment'] = {
                'enabled': old_config['enrichment'].get('enabled', False),
                'model': old_config['enrichment'].get('model', 'gpt-4o-mini'),
                'batch_size': old_config['enrichment'].get('batch_size', 50),
            }
        
        return new_config
    
    @staticmethod
    def _create_example_from_old(old_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create an example local configuration based on old format."""
        example = {}
        
        # Copy any existing settings as examples
        for section, data in old_config.items():
            if isinstance(data, dict):
                example[section] = {}
                for key, value in data.items():
                    if key in ['preset', 'model', 'enabled', 'batch_size']:
                        example[section][f"# {key}"] = value
                    else:
                        example[section][key] = value
        
        return example


def main():
    """Main CLI interface for configuration validation and migration."""
    parser = argparse.ArgumentParser(description="LLMC Configuration Validator")
    parser.add_argument("--config-dir", help="Configuration directory to validate")
    parser.add_argument("--config-file", help="Specific config file to validate")
    parser.add_argument("--validate", action="store_true", help="Validate configuration")
    parser.add_argument("--migrate", help="Migrate old config file to new format")
    parser.add_argument("--output-dir", help="Output directory for migration")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    validator = ConfigValidator()
    success = True
    
    if args.validate:
        if args.config_file:
            # Validate specific file
            success = validator.validate_file(Path(args.config_file))
        elif args.config_dir:
            # Validate directory
            config_dir = Path(args.config_dir)
            for config_file in config_dir.glob("*.toml"):
                if config_file.name.startswith(('default', 'local')):
                    if not validator.validate_file(config_file):
                        success = False
        else:
            # Validate current config
            try:
                config = Config.load()
                success = validator.validate_config_object(config)
            except Exception as e:
                print(f"Failed to load configuration: {e}")
                success = False
    
    if args.migrate:
        old_config_path = Path(args.migrate)
        output_dir = Path(args.output_dir) if args.output_dir else Path("config")
        success = ConfigMigrator.migrate_from_old_config(old_config_path, output_dir)
    
    # Print validation results
    if args.validate or not args.migrate:
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
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()