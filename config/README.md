# LLMC Configuration Management

The LLMC configuration system provides a flexible 3-tier approach to managing application settings with automatic precedence handling.

## Overview

The configuration system uses a 3-tier precedence model:
1. **Environment variables** (highest precedence)
2. **local.toml** (user overrides - git-ignored)
3. **default.toml** (system defaults)

This approach allows for flexible configuration management while maintaining sensible defaults and supporting environment-specific overrides.

## Quick Start

### 1. Initialize Configuration
```bash
# Create initial configuration structure
python -m config.cli init

# Or manually copy the example config
cp config/local.example.toml config/local.toml
```

### 2. Basic Usage
```bash
# Show current configuration
python -m config.cli show

# Get a specific value
python -m config.cli get storage.index_path

# Set a configuration value
python -m config.cli set providers.default ollama --write
```

### 3. Validate Configuration
```bash
# Validate current configuration
python -m config.cli validate

# Validate a specific file
python -m config.cli validate --config-file my_config.toml
```

## Configuration Files

### `config/default.toml`
System defaults that work out of the box. These can be overridden by user configuration.

**Key sections:**
- `embeddings`: Vector embedding settings
- `storage`: File paths for indexes and cache
- `enrichment`: Document enrichment settings
- `logging`: Logging configuration
- `providers`: LLM provider configurations
- `semantic_cache`: Caching settings
- `rag`: Retrieval-Augmented Generation settings

### `config/local.example.toml`
Example configuration file that users can copy and modify. Shows available options with helpful comments.

### `config/local.toml` (created by user)
Personal configuration overrides. This file is git-ignored and contains user-specific settings.

### `config/profiles/`
Pre-configured settings for different LLM providers:
- `claude.yml`: Anthropic Claude configuration
- `azure.yml`: Microsoft Azure OpenAI settings
- `gemini.yml`: Google Gemini API configuration
- `ollama.yml`: Local Ollama setup
- `minimax.yml`: MiniMax API settings

## Environment Variable Support

Configuration can be overridden using environment variables. The general pattern is:

```bash
export LLMC_SECTION_KEY="value"
```

Examples:
```bash
# Override storage path
export LLMC_STORAGE_INDEX_PATH="/custom/path/index.db"

# Enable enrichment
export LLMC_ENRICHMENT_ENABLED="true"

# Set default provider
export LLMC_DEFAULT_PROVIDER="ollama"

# Configure semantic cache
export SEMANTIC_CACHE_MIN_SCORE="0.8"
```

## Common Use Cases

### Local Development
```bash
# Use local Ollama with minimal overhead
cp examples/configs/basic_local.toml config/local.toml
```

### Production Deployment
```bash
# Use optimized production settings
cp examples/configs/production.toml config/local.toml
```

### Cost-Sensitive Usage
```bash
# Minimize API costs while maintaining functionality
cp examples/configs/cost_optimized.toml config/local.toml
```

### Development and Debugging
```bash
# Maximum logging and debugging features
cp examples/configs/development.toml config/local.toml
```

## Configuration Management in Scripts

### Python Integration
```python
from config import Config

# Load configuration
config = Config.load()

# Get values with fallbacks
model = config.get('embeddings.model', 'default-model')
enabled = config.getboolean('enrichment.enabled', False)

# Access nested sections
claude_config = config.section('providers.claude')
api_key = claude_config.get('api_key_env')
```

### Shell Script Integration
```bash
#!/usr/bin/env bash

# Load configuration (if Python is available)
if command -v python3 >/dev/null 2>&1; then
    eval "$(python3 -m config.cli --export-shell)"
fi

# Use configuration values
INDEX_PATH="${LLMC_STORAGE_INDEX_PATH:-.llmc/index/index_v2.db}"
ENRICHMENT_ENABLED="${LLMC_ENRICHMENT_ENABLED:-false}"

if [ "$ENRICHMENT_ENABLED" = "true" ]; then
    # Run enrichment processing
    echo "Enrichment enabled"
fi
```

## Provider Profiles

Each LLM provider has a dedicated configuration profile in `config/profiles/`:

```bash
# List available profiles
python -m config.cli profiles --list

# Show profile details
python -m config.cli profiles --name claude
```

### Profile Structure
```yaml
# config/profiles/claude.yml
name: claude
display_name: "Claude Code"
description: "Anthropic Claude Code CLI with web authentication"

provider:
  type: "claude"
  enabled: true
  api_key_env: "ANTHROPIC_API_KEY"

model:
  name: "claude-sonnet-4-20250514"
  parameters:
    temperature: 0.1
    top_p: 0.9
```

## Migration from Old Configuration

If you have an existing `llmc.toml` file:

```bash
# Migrate to new 3-tier system
python -m config.cli migrate llmc.toml --output-dir config

# This will create:
# - config/default.toml (from old settings)
# - config/local.example.toml (commented examples)
```

## Validation and Debugging

### Configuration Validation
```bash
# Basic validation
python -m config.cli validate

# Detailed validation with verbose output
python -m config.cli validate --verbose
```

### Debug Configuration Loading
```python
from config import Config
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Load configuration
config = Config.load()
print(config)
```

## Best Practices

1. **Start with defaults**: Use `config/default.toml` as a foundation
2. **Only override what you need**: Copy `local.example.toml` to `local.toml` and modify only necessary settings
3. **Use environment variables for secrets**: Don't put API keys in configuration files
4. **Validate before deployment**: Use `python -m config.cli validate` to check configuration
5. **Use profiles for consistency**: Leverage provider profiles for standardized setup
6. **Version control wisely**: Keep `default.toml` in git, but git-ignore `local.toml`

## Troubleshooting

### Configuration Not Loading
1. Check if configuration files exist and are valid TOML
2. Ensure Python path includes the config module
3. Verify file permissions
4. Check for TOML syntax errors

### Environment Variables Not Working
1. Ensure variable names match the expected pattern (`LLMC_SECTION_KEY`)
2. Check that variables are exported in the correct shell context
3. Verify environment variable precedence (they override all config files)

### Provider Not Working
1. Check provider profile configuration in `config/profiles/`
2. Verify required environment variables are set
3. Test provider connectivity manually
4. Review provider-specific documentation

## Advanced Usage

### Custom Configuration Directory
```python
from pathlib import Path
from config import Config

config = Config.load(Path("/custom/config/path"))
```

### Programmatic Configuration Updates
```python
from config import Config

config = Config.load()

# Update configuration in memory
config.set('providers.default', 'ollama')
config.set('storage.index_path', '/new/path/index.db')

# Write to local.toml
# (Implementation would depend on your specific needs)
```

### Configuration Validation in CI/CD
```bash
#!/bin/bash
# CI/CD validation script

set -e

# Validate configuration
python -m config.cli validate

# Check required environment variables
required_vars=("ANTHROPIC_API_KEY" "AZURE_OPENAI_ENDPOINT")
for var in "${required_vars[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "Error: Required environment variable $var is not set"
        exit 1
    fi
done

echo "Configuration validation passed"
```

This configuration system provides a robust foundation for managing LLMC settings across different environments and use cases while maintaining simplicity and flexibility.