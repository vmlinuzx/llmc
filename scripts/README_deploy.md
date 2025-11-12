# LLMC Template Deployer

A powerful tool for deploying LLMC templates to target repositories with intelligent path adjustment, configuration merging, and rollback support.

## Overview

The LLMC Template Deployer (`deploy_template.py`) is a Python script that takes an extracted LLMC template and intelligently deploys it to target repositories. It handles all the complexity of:

- Backing up existing `llmc/` directories
- Adjusting hardcoded path references
- Merging configurations intelligently
- Updating script references
- Supporting dry-run mode for safe previews
- Providing rollback capabilities

## Quick Start

### Basic Usage

```bash
# Deploy template to current directory
python3 scripts/deploy_template.py .

# Or use the llmc wrapper
./scripts/llmc deploy .
```

### Common Commands

```bash
# Deploy to a specific repository
llmc deploy /path/to/my/repo

# Preview changes without applying (dry-run)
llmc deploy /path/to/repo --dry-run

# Force deployment (overwrite existing llmc/ directory)
llmc deploy /path/to/repo --force

# Deploy without creating backup
llmc deploy /path/to/repo --no-backup
```

## Command Interface

The deployer provides a `llmc deploy <target_dir>` command interface with the following options:

### Required Arguments

- `target_dir` - Path to the target repository where the template should be deployed

### Optional Flags

- `--template PATH` - Path to the template directory (default: `template`)
- `--llmc-path PATH` - Path for the llmc directory in target (default: `llmc`)
- `--dry-run` - Preview changes without applying them
- `--no-backup` - Skip creating backup of existing llmc directory
- `--force` - Force deployment even if llmc directory exists
- `--verbose` - Enable verbose output
- `--rollback BACKUP` - Rollback to a specific backup

## Features

### 1. Intelligent File Deployment

- Copies all template files to the target's `llmc/` folder
- Preserves file permissions and attributes
- Handles binary and text files appropriately
- Creates necessary parent directories

### 2. Automatic Backup

- Creates timestamped backups of existing `llmc/` directories
- Stores backups in `llmc_backups/` directory
- Backup naming: `llmc_YYYYMMDD_HHMMSS`
- Automatic backup before any modifications

### 3. Path Adjustment

The deployer automatically detects and adjusts hardcoded references:

**Shell Scripts:**
```bash
# Before: tools/script.sh
# After:  llmc/tools/script.sh

# Before: ../config/file.toml
# After:  ../llmc/config/file.toml
```

**Python Scripts:**
```python
# Before: from tools.rag import indexer
# After:  from llmc.tools.rag import indexer
```

**Configuration Files:**
```json
# Before: "scripts": ["scripts/"]
# After:  "scripts": ["llmc/scripts/"]
```

### 4. Configuration Merging

Intelligently merges configuration files:

**Priority Order:**
1. Environment variables
2. `llmc/config/local.toml` (user config - preserved)
3. `llmc/config/default.toml` (system defaults - deployed)

**Behavior:**
- Preserves existing `local.toml` configurations
- Creates `local.example.toml` if it doesn't exist
- Deploys all template configuration files
- Warns on configuration conflicts

### 5. Script Reference Updates

Updates script references to point to the new `llmc/` structure:

- Updates `SCRIPT_ROOT` references in bash scripts
- Adjusts Python import paths
- Fixes configuration file references
- Updates tool and module paths

### 6. Dry-Run Mode

Preview all changes before applying:

```bash
llmc deploy /path/to/repo --dry-run
```

Shows:
- Files to be created
- Files to be updated
- Files to be backed up
- Configuration merging plans
- Path adjustment summary

### 7. Rollback Capability

Rollback to a previous backup:

```bash
# List available backups
ls llmc_backups/

# Rollback to specific backup
llmc deploy /path/to/repo --rollback llmc_20241111_120819
```

Rollback process:
1. Removes current `llmc/` directory
2. Restores backup to `llmc/` directory
3. Preserves all original files and permissions

## Usage Examples

### Example 1: Basic Deployment

```bash
# Deploy template to a new repository
cd /path/to/my/new/repo
llmc deploy .

# Output:
# ===== LLMC Template Deployment Starting =====
# Target directory: /path/to/my/new/repo
# Template source: /path/to/template
# LLMC path in target: llmc
# Dry run mode: False
# 
# Creating backup: llmc_backups/llmc_20241111_120819
# Backup created successfully.
# 
# Analyzing changes...
# Analysis complete. 45 files to deploy.
# 
# Applying changes...
# Creating: llmc/README.md
# Creating: llmc/scripts/claude_wrap.sh
# Creating: llmc/config/default.toml
# ...
# 
# Deployment completed successfully!
```

### Example 2: Dry-Run Preview

```bash
# Preview changes without applying
llmc deploy /path/to/existing/repo --dry-run

# Output:
# ===== LLMC Template Deployment Starting =====
# 
# DEPLOYMENT PREVIEW (Dry Run)
# ============================
# 
# BACKUP (1 items):
#   llmc/config/local.toml
#     Reason: Preserving existing local.toml configuration
# 
# CREATE (42 items):
#   llmc/README.md
#   llmc/scripts/claude_wrap.sh
#   llmc/scripts/codex_wrap.sh
#   ...
# 
# UPDATE (3 items):
#   llmc/config/default.toml
#     Reason: Adjusting paths for new structure
# ...
```

### Example 3: Force Deployment

```bash
# Deploy to repository with existing llmc/ directory
llmc deploy /path/to/repo --force

# Output:
# Creating backup: llmc_backups/llmc_20241111_120819
# Backing up: llmc/scripts/existing_script.sh
# Updating: llmc/config/default.toml
# ...
```

### Example 4: Custom Template Path

```bash
# Use custom template location
llmc deploy /path/to/repo --template /custom/path/to/template

# Or use relative path
llmc deploy /path/to/repo --template ./my-templates/custom-llmc
```

### Example 5: Rollback

```bash
# Rollback to previous deployment
llmc deploy /path/to/repo --rollback llmc_20241111_120819

# Output:
# Rolling back to: llmc_backups/llmc_20241111_120819
# Rollback completed successfully.
```

## Advanced Features

### Path Adjustment Patterns

The deployer recognizes and adjusts these path patterns:

1. **Relative Path Adjustments:**
   - `../tools` → `../llmc/tools`
   - `../scripts` → `../llmc/scripts`
   - `../config` → `../llmc/config`

2. **Directory References:**
   - `tools/` → `llmc/tools/`
   - `scripts/` → `llmc/scripts/`
   - `config/` → `llmc/config/`

3. **Module Imports:**
   - `from tools.rag import indexer` → `from llmc.tools.rag import indexer`
   - `import scripts.module` → `import llmc.scripts.module`

### Configuration Handling

**Local Configuration (Preserved):**
```
llmc/config/local.toml  # User preferences - never overwritten
```

**Default Configuration (Deployed):**
```
llmc/config/default.toml  # System defaults - can be updated
```

**Example Configuration:**
```toml
# llmc/config/default.toml
[embeddings]
preset = "e5"
model = "intfloat/e5-base-v2"

[storage]
index_path = ".llmc/index/index_v2.db"

[enrichment]
enabled = false
model = "gpt-4o-mini"
batch_size = 50
```

### Backup Management

Backups are created in the target repository:

```
my-repo/
├── llmc/                    # Current deployment
└── llmc_backups/
    ├── llmc_20241111_120819/
    │   ├── config/
    │   ├── scripts/
    │   └── tools/
    ├── llmc_20241110_154532/
    │   ├── config/
    │   ├── scripts/
    │   └── tools/
    └── ...
```

### Metadata Tracking

Deployment metadata is saved to:

```
llmc/.llmc_deploy_metadata.json
```

Contains:
- Deployment timestamp
- Source template path
- Applied changes
- Backup location
- Configuration merge status

## Error Handling

The deployer provides comprehensive error handling:

### Validation Errors

```
Error: Target directory does not exist: /path/to/repo
Error: Template directory does not exist: /path/to/template
Error: Target already has llmc directory. Use --force to overwrite.
```

### File System Errors

```
Error: Failed to create backup: Permission denied
Error: Failed to apply change for llmc/config/file.toml: Disk full
```

### Rollback Errors

```
Error: No backup available for rollback.
Warning: Rollback failed: Manual intervention may be required.
```

## Best Practices

1. **Always Use Dry-Run First:**
   ```bash
   llmc deploy /path/to/repo --dry-run
   ```

2. **Check Existing Configurations:**
   ```bash
   # Before deployment, check for existing config
   ls -la /path/to/repo/llmc/config/
   ```

3. **Use Meaningful Commit Messages:**
   ```bash
   git add -A && git commit -m "Deploy LLMC template - $(date)"
   ```

4. **Regular Backups:**
   ```bash
   # Rollback if needed
   llmc deploy /path/to/repo --rollback llmc_20241111_120819
   ```

5. **Test in Staging First:**
   ```bash
   # Deploy to test repository first
   llmc deploy /path/to/test/repo --dry-run
   ```

## Troubleshooting

### Common Issues

**Issue: "Template directory does not exist"**
```bash
# Solution: Check template path
llmc deploy /path/to/repo --template /correct/path/to/template
```

**Issue: "Permission denied"**
```bash
# Solution: Check directory permissions
chmod 755 /path/to/repo
llmc deploy /path/to/repo
```

**Issue: "Path adjustments not working"**
```bash
# Solution: Check file types
llmc deploy /path/to/repo --verbose
# Look for files that need manual adjustment
```

**Issue: "Rollback not working"**
```bash
# Solution: Check backup exists
ls llmc_backups/
# Use full backup path
llmc deploy /path/to/repo --rollback llmc_20241111_120819
```

### Debug Mode

Enable verbose output for detailed information:

```bash
llmc deploy /path/to/repo --verbose
```

Shows:
- File operations in detail
- Path adjustment calculations
- Configuration merge decisions
- Backup creation progress

## Exit Codes

- `0` - Success
- `1` - General error
- `2` - Validation error
- `3` - File system error
- `4` - Rollback failure

## Performance Considerations

- Large templates (>1000 files) may take several minutes
- Backup creation doubles deployment time
- Path adjustment uses regex and may be slow on large files
- Consider using `--no-backup` for faster deployment in CI/CD

## Security Notes

- Always review dry-run output before deploying
- Check backup directory size in repositories with large files
- Validate template source before deployment
- Use `--force` only when necessary

## Integration with CI/CD

Example GitHub Actions workflow:

```yaml
name: Deploy LLMC Template

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Deploy LLMC Template
        run: |
          # Preview changes
          llmc deploy . --dry-run
          
          # Deploy (skip backup for CI)
          llmc deploy . --no-backup --verbose
```

## Development

### Testing

```bash
# Test in isolated environment
mkdir -p /tmp/test-deploy
cp -r template /tmp/test-deploy/
cd /tmp/test-deploy
llmc deploy . --dry-run --verbose
```

### Customization

The script can be extended by modifying the `TemplateDeployer` class in `deploy_template.py`:

- Add custom path adjustment patterns
- Implement custom configuration merge strategies
- Add new file type handlers
- Integrate with external systems

## License

This tool is part of the LLMC (LLM Commander) project.

## Support

For issues and questions:
- Check troubleshooting section
- Review deployment logs
- Enable verbose mode for detailed output
- Create backup before major changes
