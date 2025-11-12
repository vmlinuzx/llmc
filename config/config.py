#!/usr/bin/env python3
"""
LLMC Configuration Management System

Provides 3-tier configuration loading:
1. Environment variables (highest precedence)
2. local.toml (user overrides)
3. default.toml (system defaults)

Usage:
    from config import Config
    
    # Load configuration with automatic precedence
    config = Config.load()
    
    # Get values with fallbacks
    model = config.get('embeddings.model', 'default-model')
    enabled = config.getboolean('enrichment.enabled', False)
    
    # Access nested sections
    claude_enabled = config.get('providers.claude.enabled', False)
"""

import os
import sys
import toml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging

# Configure logging
logger = logging.getLogger(__name__)


class Config:
    """
    Configuration manager with 3-tier loading precedence:
    1. Environment variables
    2. local.toml (user config)
    3. default.toml (system defaults)
    """
    
    def __init__(self, data: Dict[str, Any]):
        self._data = data or {}
        self._env_cache = {}
        self._load_environment_cache()
    
    @classmethod
    def load(cls, config_dir: Optional[Path] = None) -> 'Config':
        """
        Load configuration with automatic precedence.
        
        Args:
            config_dir: Directory containing config files. Defaults to 'config/' relative to this module.
        
        Returns:
            Config instance with merged settings from all sources.
        """
        if config_dir is None:
            # Try to find config directory relative to this file
            current_file = Path(__file__)
            config_dir = current_file.parent / "config"
        
        # Load default configuration
        default_config = cls._load_config_file(config_dir / "default.toml")
        if default_config is None:
            default_config = {}
        
        # Load local configuration (user overrides)
        local_config = cls._load_config_file(config_dir / "local.toml")
        if local_config is None:
            local_config = {}
        
        # Merge: local > default
        merged_data = cls._deep_merge(default_config, local_config)
        
        return cls(merged_data)
    
    @staticmethod
    def _load_config_file(file_path: Path) -> Optional[Dict[str, Any]]:
        """Load a TOML configuration file if it exists."""
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r') as f:
                return toml.load(f)
        except Exception as e:
            logger.error(f"Failed to load config file {file_path}: {e}")
            return None
    
    @staticmethod
    def _deep_merge(default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge two dictionaries, with override taking precedence."""
        result = default.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _load_environment_cache(self):
        """Load environment variables that correspond to config settings."""
        # Common environment variable mappings
        env_mappings = {
            # Embeddings
            'LLMC_EMBEDDINGS_MODEL': 'embeddings.model',
            'LLMC_EMBEDDINGS_PRESET': 'embeddings.preset',
            
            # Storage
            'LLMC_STORAGE_INDEX_PATH': 'storage.index_path',
            'LLMC_STORAGE_CACHE_PATH': 'storage.cache_path',
            
            # Enrichment
            'LLMC_ENRICHMENT_ENABLED': 'enrichment.enabled',
            'LLMC_ENRICHMENT_MODEL': 'enrichment.model',
            'LLMC_ENRICHMENT_BATCH_SIZE': 'enrichment.batch_size',
            
            # Logging
            'LLMC_LOG_LEVEL': 'logging.level',
            'LLMC_LOG_FILE': 'logging.file',
            'LLMC_LOG_CONSOLE': 'logging.console_output',
            
            # Concurrency
            'LLMC_CONCURRENCY': 'concurrency.enabled',
            'LLMC_CONCURRENCY_MAX_TASKS': 'concurrency.max_concurrent_tasks',
            'LLMC_CONCURRENCY_TIMEOUT': 'concurrency.task_timeout',
            
            # Semantic cache
            'SEMANTIC_CACHE_ENABLE': 'semantic_cache.enabled',
            'SEMANTIC_CACHE_DISABLE': 'semantic_cache.enabled',
            'SEMANTIC_CACHE_MIN_SCORE': 'semantic_cache.min_score',
            
            # Deep research
            'DEEP_RESEARCH_ENABLED': 'deep_research.enabled',
            'DEEP_RESEARCH_ALLOW_AUTO': 'deep_research.auto_route_override',
            
            # Providers
            'LLMC_DEFAULT_PROVIDER': 'providers.default',
            'ANTHROPIC_API_KEY': 'providers.claude.api_key_env',
            'AZURE_OPENAI_ENDPOINT': 'providers.azure.endpoint_env',
            'AZURE_OPENAI_KEY': 'providers.azure.key_env',
            'AZURE_OPENAI_DEPLOYMENT': 'providers.azure.deployment_env',
            'GOOGLE_API_KEY': 'providers.gemini.api_key_env',
            'MINIMAX_BASE_URL': 'providers.minimax.base_url_env',
            'MINIMAXKEY2': 'providers.minimax.api_key_env',
            'MINIMAX_MODEL': 'providers.minimax.model_env',
            
            # RAG
            'LLMC_RAG_INDEX_PATH': 'rag.index_path',
            'CODEX_WRAP_DISABLE_RAG': 'rag.enabled',
            
            # Security
            'DANGEROUSLY_SKIP_PERMISSIONS': 'security.dangerously_skip_permissions',
            'YOLO_MODE': 'security.yolo_mode',
            
            # Development
            'LLMC_DEBUG': 'development.debug',
            'LLMC_TRACE_LOGGING': 'development.trace_logging',
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                self._env_cache[config_path] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value with environment variable precedence.
        
        Args:
            key: Configuration key (supports dot notation, e.g., 'providers.claude.enabled')
            default: Default value if key is not found
        
        Returns:
            Configuration value or default.
        """
        # Check environment cache first
        if key in self._env_cache:
            return self._env_cache[key]
        
        # Navigate through nested structure
        keys = key.split('.')
        value = self._data
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def getboolean(self, key: str, default: bool = False) -> bool:
        """Get a boolean configuration value."""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    
    def getint(self, key: str, default: int = 0) -> int:
        """Get an integer configuration value."""
        value = self.get(key, default)
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def getfloat(self, key: str, default: float = 0.0) -> float:
        """Get a float configuration value."""
        value = self.get(key, default)
        if isinstance(value, float):
            return value
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def getlist(self, key: str, default: List = None) -> List:
        """Get a list configuration value."""
        value = self.get(key, default or [])
        if isinstance(value, list):
            return value
        return [value] if value else []
    
    def set(self, key: str, value: Any):
        """Set a configuration value."""
        keys = key.split('.')
        current = self._data
        
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Set the value
        current[keys[-1]] = value
    
    def has_key(self, key: str) -> bool:
        """Check if a configuration key exists."""
        keys = key.split('.')
        value = self._data
        
        try:
            for k in keys:
                value = value[k]
            return True
        except (KeyError, TypeError):
            return False
    
    def section(self, section: str) -> 'Config':
        """Get a Config object for a specific section."""
        section_data = self.get(section, {})
        if isinstance(section_data, dict):
            return Config(section_data)
        return Config({})
    
    def to_dict(self) -> Dict[str, Any]:
        """Return the configuration as a dictionary."""
        return self._data.copy()
    
    def keys(self) -> List[str]:
        """Return all top-level configuration keys."""
        return list(self._data.keys())
    
    def __repr__(self):
        return f"Config({len(self._data)} sections: {', '.join(self.keys())})"
    
    def __str__(self):
        return str(self._data)


def load_config(config_dir: Optional[Path] = None) -> Config:
    """Convenience function to load configuration."""
    return Config.load(config_dir)


def get_config_value(key: str, default: Any = None, config_dir: Optional[Path] = None) -> Any:
    """Convenience function to get a single configuration value."""
    config = Config.load(config_dir)
    return config.get(key, default)


def is_enabled(key: str, config_dir: Optional[Path] = None) -> bool:
    """Convenience function to check if a feature is enabled."""
    config = Config.load(config_dir)
    return config.getboolean(key, False)


# CLI functions for shell integration
def export_shell_config():
    """Export configuration as shell environment variables."""
    config = Config.load()
    
    # Export key configuration as environment variables
    exports = [
        f"export LLMC_EMBEDDINGS_MODEL='{config.get('embeddings.model', '')}'",
        f"export LLMC_STORAGE_INDEX_PATH='{config.get('storage.index_path', '')}'",
        f"export LLMC_ENRICHMENT_ENABLED='{config.getboolean('enrichment.enabled', False)}'",
        f"export LLMC_RAG_ENABLED='{config.getboolean('rag.enabled', True)}'",
        f"export LLMC_SEMANTIC_CACHE_ENABLED='{config.getboolean('semantic_cache.enabled', True)}'",
        f"export LLMC_DEFAULT_PROVIDER='{config.get('providers.default', 'claude')}'",
        f"export LLMC_LOG_LEVEL='{config.get('logging.level', 'INFO')}'",
    ]
    
    return '\n'.join(exports)


if __name__ == "__main__":
    # CLI mode for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="LLMC Configuration Manager")
    parser.add_argument("--config-dir", help="Configuration directory path")
    parser.add_argument("--get", help="Get configuration value by key")
    parser.add_argument("--export-shell", action="store_true", help="Export as shell variables")
    parser.add_argument("--validate", action="store_true", help="Validate configuration")
    parser.add_argument("--debug", action="store_true", help="Debug output")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    
    config = Config.load(Path(args.config_dir) if args.config_dir else None)
    
    if args.get:
        value = config.get(args.get)
        print(value)
    elif args.export_shell:
        print(export_shell_config())
    elif args.validate:
        # Validation would go here
        print("Configuration validation not yet implemented")
    else:
        # Default: show all configuration
        print("LLMC Configuration:")
        print("=" * 50)
        for section in config.keys():
            print(f"\n[{section}]")
            section_config = config.section(section)
            for key in section_config.keys():
                value = section_config.get(key)
                print(f"  {key} = {value}")