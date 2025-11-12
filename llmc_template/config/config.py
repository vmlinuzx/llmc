#!/usr/bin/env python3
"""
LLMC Configuration Management System

Provides 3-tier configuration hierarchy:
1. Environment Variables (highest priority)
2. Local Config (config/local.toml) 
3. Default Config (config/default.toml)
"""

import os
import toml
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages 3-tier configuration with precedence rules."""
    
    def __init__(self, project_root: str = None):
        """Initialize config manager with project root."""
        if project_root is None:
            project_root = os.getcwd()
        
        self.project_root = Path(project_root)
        self.config_dir = self.project_root / "config"
        self.config_dir.mkdir(exist_ok=True)
        
        self._load_all_configs()
    
    def _load_all_configs(self):
        """Load all configuration files in precedence order."""
        # 1. Load default config (lowest priority)
        self.default_config = self._load_config_file("default.toml")
        
        # 2. Load local config (medium priority)
        self.local_config = self._load_config_file("local.toml")
        
        # 3. Environment variables (highest priority)
        self.env_config = self._load_env_vars()
        
        logger.info("Configuration loaded successfully")
    
    def _load_config_file(self, filename: str) -> Dict[str, Any]:
        """Load configuration from TOML file."""
        config_file = self.config_dir / filename
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    return toml.load(f)
            except Exception as e:
                logger.error(f"Error loading {filename}: {e}")
                return {}
        else:
            logger.debug(f"Config file not found: {filename}")
            return {}
    
    def _load_env_vars(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        
        # Map environment variables to config paths
        env_mappings = {
            # Provider configurations
            'CLAUDE_API_KEY': ('providers', 'claude', 'api_key'),
            'GEMINI_API_KEY': ('providers', 'gemini', 'api_key'),
            'OPENAI_API_KEY': ('providers', 'openai', 'api_key'),
            'AZURE_API_KEY': ('providers', 'azure', 'api_key'),
            
            # LLM settings
            'LLM_MODEL': ('llm', 'model'),
            'LLM_TEMPERATURE': ('llm', 'temperature'),
            'LLM_MAX_TOKENS': ('llm', 'max_tokens'),
            
            # RAG settings
            'RAG_EMBEDDING_MODEL': ('embeddings', 'model'),
            'RAG_INDEX_PATH': ('storage', 'index_path'),
            'RAG_DB_PATH': ('storage', 'database_path'),
            
            # Enrichment settings
            'ENRICHMENT_ENABLED': ('enrichment', 'enabled'),
            'ENRICHMENT_MODEL': ('enrichment', 'model'),
            'ENRICHMENT_BATCH_SIZE': ('enrichment', 'batch_size'),
            
            # Paths
            'LLMC_PROJECT_PATH': ('paths', 'project_root'),
            'LLMC_CACHE_PATH': ('paths', 'cache_dir'),
            'LLMC_TEMP_PATH': ('paths', 'temp_dir'),
        }
        
        for env_var, config_path in env_mappings.items():
            if env_var in os.environ:
                self._set_nested_value(config, config_path, os.environ[env_var])
        
        return config
    
    def _set_nested_value(self, config: Dict, path: tuple, value: Any):
        """Set a value in nested dictionary using path tuple."""
        current = config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = self._convert_value(value)
    
    def _convert_value(self, value: str) -> Any:
        """Convert string environment variable to appropriate type."""
        # Try to convert to int
        if value.isdigit():
            return int(value)
        
        # Try to convert to float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Try to convert to boolean
        if value.lower() in ('true', '1', 'yes', 'on'):
            return True
        elif value.lower() in ('false', '0', 'no', 'off'):
            return False
        
        # Return as string
        return value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with precedence."""
        keys = key.split('.')
        
        # 1. Check environment config (highest priority)
        value = self._get_nested_value(self.env_config, keys)
        if value is not None:
            return value
        
        # 2. Check local config (medium priority)
        value = self._get_nested_value(self.local_config, keys)
        if value is not None:
            return value
        
        # 3. Check default config (lowest priority)
        value = self._get_nested_value(self.default_config, keys)
        if value is not None:
            return value
        
        # Return default if nothing found
        return default
    
    def _get_nested_value(self, config: Dict, keys: list) -> Any:
        """Get value from nested dictionary using key list."""
        current = config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
    
    def set(self, key: str, value: Any, level: str = 'local'):
        """Set configuration value at specified level."""
        if level == 'local':
            self._set_nested_value(self.local_config, key.split('.'), value)
            self._save_local_config()
        else:
            raise ValueError(f"Only 'local' level is writable")
    
    def _save_local_config(self):
        """Save local configuration to file."""
        local_file = self.config_dir / "local.toml"
        
        try:
            with open(local_file, 'w') as f:
                toml.dump(self.local_config, f)
            logger.info(f"Saved local configuration to {local_file}")
        except Exception as e:
            logger.error(f"Error saving local config: {e}")
    
    def show(self, key: str = None) -> Dict[str, Any]:
        """Show configuration values."""
        if key:
            return self.get(key)
        else:
            return {
                'default': self.default_config,
                'local': self.local_config,
                'environment': self.env_config,
                'effective': self.get_effective_config()
            }
    
    def get_effective_config(self) -> Dict[str, Any]:
        """Get the effective configuration after applying precedence."""
        # Start with default config
        effective = self._deep_merge(self.default_config, self.local_config)
        effective = self._deep_merge(effective, self.env_config)
        return effective
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def validate(self) -> Dict[str, Any]:
        """Validate configuration and return any issues."""
        issues = []
        warnings = []
        
        effective_config = self.get_effective_config()
        
        # Check for required fields
        required_fields = [
            ('embeddings', 'preset'),
            ('storage', 'index_path'),
        ]
        
        for section, field in required_fields:
            if self.get(f"{section}.{field}") is None:
                issues.append(f"Missing required field: {section}.{field}")
        
        # Check for common issues
        if effective_config.get('providers', {}).get('claude', {}).get('api_key') is None:
            warnings.append("CLAUDE_API_KEY not set")
        
        if effective_config.get('storage', {}).get('index_path') is None:
            warnings.append("RAG index path not configured")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }

# Global config instance
_config_manager = None

def get_config() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

def get(key: str, default: Any = None) -> Any:
    """Get configuration value using global config manager."""
    return get_config().get(key, default)

def set(key: str, value: Any, level: str = 'local'):
    """Set configuration value using global config manager."""
    get_config().set(key, value, level)

def show(key: str = None) -> Dict[str, Any]:
    """Show configuration using global config manager."""
    return get_config().show(key)

def validate() -> Dict[str, Any]:
    """Validate configuration using global config manager."""
    return get_config().validate()

if __name__ == "__main__":
    # Command-line interface
    import argparse
    
    parser = argparse.ArgumentParser(description="LLMC Configuration Management")
    parser.add_argument('command', choices=['get', 'set', 'show', 'validate'],
                       help='Configuration command to execute')
    parser.add_argument('key', nargs='?', help='Configuration key (for get/set)')
    parser.add_argument('value', nargs='?', help='Configuration value (for set)')
    parser.add_argument('--level', default='local', help='Configuration level')
    
    args = parser.parse_args()
    
    if args.command == 'get':
        if args.key:
            value = get(args.key)
            print(f"{args.key} = {value}")
        else:
            config = get_config().show()
            print("Full configuration:")
            import json
            print(json.dumps(config, indent=2))
    
    elif args.command == 'set':
        if not args.key or args.value is None:
            print("Error: 'set' command requires key and value")
            exit(1)
        set(args.key, args.value, args.level)
        print(f"Set {args.key} = {args.value}")
    
    elif args.command == 'show':
        config = get_config().show(args.key)
        print("Configuration:")
        import json
        print(json.dumps(config, indent=2))
    
    elif args.command == 'validate':
        validation = validate()
        print("Configuration validation:")
        print(f"Valid: {validation['valid']}")
        if validation['issues']:
            print("Issues:")
            for issue in validation['issues']:
                print(f"  - {issue}")
        if validation['warnings']:
            print("Warnings:")
            for warning in validation['warnings']:
                print(f"  - {warning}")