# Living Template System - Complete Usage Guide

## Overview

The Living Template System allows you to extract portable components from your LLM Commander project and deploy them to other repositories. This solves the "dog eating its own food" problem by creating a clean, maintainable way to share LLM Commander's "magic" across multiple projects.

## Quick Start

### 1. Extract Template from LLM Commander

```bash
# Navigate to your LLM Commander project
cd /path/to/your/llmc-commander

# Extract portable components
python scripts/extract_template.py --output llmc_template

# This creates llmc_template/ with all the portable components
```

### 2. Deploy to Target Project

```bash
# Deploy to any target repository
python scripts/deploy_template.py /path/to/your/target/project

# Or use dry-run to preview changes first
python scripts/deploy_template.py --dry-run /path/to/your/target/project
```

### 3. Verify Deployment

```bash
# Check what was created in target
cd /path/to/your/target/project
ls -la llmc/

# Test the magic works
./llmc/scripts/claude_wrap.sh "test context management"
```

## What's Included

### Components Extracted:
- **Scripts**: `claude_wrap.sh`, `codex_wrap.sh`, `gemini_wrap.sh`, etc.
- **Configuration**: 3-tier config system (default.toml, local.toml, environment)
- **Tools**: RAG system, cache, diagnostics
- **Documentation**: AGENTS.md, CONTRACTS.md, routing docs
- **Adapters**: Provider-specific templates

### Components Excluded:
- Template builder UI
- Web applications
- Research documents
- Test repositories

## Configuration System

### 3-Tier Precedence:
1. **Environment Variables** (highest priority)
2. **Local Config** (`config/local.toml`)  
3. **Default Config** (`config/default.toml`)

### Example Usage:
```bash
# Set via environment
export CLAUDE_API_KEY="your-key"
export GEMINI_API_KEY="your-key"

# Or create local override
cp config/local.example.toml config/local.toml
# Edit local.toml with your preferences
```

## File Structure

### In Your LLM Commander (Source):
```
llmc-commander/
├── scripts/
│   ├── extract_template.py      ← Extractor
│   ├── deploy_template.py       ← Deployer
│   └── ...                      ← All other scripts
├── config/
├── tools/
└── ...                          ← Your complete system
```

### In Target Projects:
```
target_project/
├── target_existing_files/       ← Unchanged
└── llmc/                        ← NEW folder with magic
    ├── scripts/                 ← claude_wrap, codex_wrap, etc.
    ├── config/                  ← Configuration files
    ├── tools/                   ← RAG system, cache, etc.
    └── ...                      ← Portable components only
```

## Testing & Validation

### 1. Dry Run Test:
```bash
python scripts/deploy_template.py --dry-run /path/to/test/project
```

### 2. Full Deployment Test:
```bash
python scripts/deploy_template.py /path/to/test/project
```

### 3. Test Functionality:
```bash
cd /path/to/test/project

# Test context management
./llmc/scripts/claude_wrap.sh "analyze this codebase"

# Test RAG indexing
./llmc/scripts/rag_refresh.sh

# Check configuration
./llmc/config/validate.py
```

## Advanced Usage

### Selective Component Extraction:

Edit `scripts/extract_template.py` to customize components:

```python
# In extract_component() function
components = {
    "scripts": {
        "claude_wrap.sh": {"patterns": ["config/default.toml"]},
        "codex_wrap.sh": {"patterns": ["config/default.toml"]},
        # ... other scripts
    },
    "tools": {
        "rag/": {"exclude": ["requirements.txt"]},
        "cache/": {},
        "diagnostics/": {},
    },
    # ... more components
}
```

### Custom Configuration:

1. **Environment Variables**: Set at runtime
2. **Local Config**: Project-specific overrides  
3. **Default Config**: System-wide defaults

### Rollback Support:

```bash
# Backup created automatically during deployment
# Restore from backup if needed:
cp /path/to/target/project/llmc/.backup/* /path/to/target/project/llmc/
```

## Troubleshooting

### Common Issues:

1. **Permission Errors**:
   ```bash
   chmod +x llmc/scripts/*.sh
   ```

2. **Python Path Issues**:
   ```bash
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/tools"
   ```

3. **Configuration Problems**:
   ```bash
   python llmc/config/validate.py
   ```

### Debug Mode:
```bash
# Enable verbose logging
export LLMC_DEBUG=1
./llmc/scripts/claude_wrap.sh "test"
```

## Best Practices

1. **Test First**: Always use `--dry-run` before actual deployment
2. **Backup Projects**: Make sure target projects are in version control
3. **Local Config**: Use `config/local.toml` for project-specific settings
4. **Environment Variables**: Prefer env vars for API keys and secrets
5. **Incremental Updates**: Re-extract and re-deploy when LLM Commander improves

## Update Strategy

### Manual Control (Current):
1. Make improvements to LLM Commander
2. When ready, re-extract template
3. Re-deploy to target projects when stable

### Future (On Backlog):
- Automatic update notifications
- Selective component updates
- Multi-consumer management
- Update conflict resolution

## Support

For issues:
1. Check `scripts/deploy_template.py` logs
2. Review `config/validate.py` output
3. Test on fresh target project first
4. Use `--dry-run` for debugging

## Summary

The Living Template System gives you:
✅ **Clean deployment** - Target repos get organized `llmc/` folder  
✅ **Manual control** - You decide when to update other projects  
✅ **Preservation** - Original LLM Commander stays untouched  
✅ **Flexibility** - 3-tier configuration for any environment  
✅ **Safety** - Dry-run and rollback capabilities  

You now have a way to spread the LLM Commander "magic" across all your projects while keeping everything organized and maintainable!