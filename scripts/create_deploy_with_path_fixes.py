#!/usr/bin/env python3
"""
Create a deploy.py script that includes path resolution fixes
for scripts deployed to llmc subdirectories.
"""

def create_fixed_deploy_py():
    deploy_content = '''#!/usr/bin/env python3
"""
Deploy LLM Commander template to target directory with proper path resolution.
"""

import os
import sys
import shutil
import argparse
from pathlib import Path

def fix_script_paths(deployed_dir):
    """Fix path references in deployed scripts to work from llmc subdirectory"""
    
    scripts_dir = deployed_dir / 'scripts'
    if not scripts_dir.exists():
        return
    
    # Path fixes for scripts deployed to llmc/scripts/
    path_fixes = {
        # llmc.toml is now at the same level as scripts directory
        'llmc.toml': '../llmc.toml',
        # Tools directory is two levels up
        '../tools/': '../../tools/',
        # Config directory is two levels up  
        '../config/': '../../config/',
        # Scripts reference other scripts
        '../scripts/': '../../scripts/',
        # Common patterns
        'source ../': 'source ../../',
        'cd ..': 'cd ../',
    }
    
    for script_file in scripts_dir.glob('*.sh'):
        print(f"🔧 Fixing paths in: {script_file}")
        
        with open(script_file, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Apply path fixes
        for old_path, new_path in path_fixes.items():
            content = content.replace(old_path, new_path)
        
        # Special fixes for specific scripts
        if script_file.name == 'claude_wrap.sh':
            # claude_wrap.sh needs to find configs and tools
            if '../llmc.toml' not in content:
                # Add config path resolution
                config_insert = '''
# Find config directory (scripts/ is in llmc/, so config is one level up)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$LLMC_ROOT/llmc.toml"

# Source config if it exists
if [ -f "$CONFIG_FILE" ]; then
    export LLMC_CONFIG="$CONFIG_FILE"
fi
'''
                # Insert config resolution after initial comments
                lines = content.split('\\n')
                insert_idx = 0
                for i, line in enumerate(lines):
                    if not line.strip().startswith('#') and line.strip():
                        insert_idx = i
                        break
                
                lines.insert(insert_idx, config_insert)
                content = '\\n'.join(lines)
        
        if content != original_content:
            with open(script_file, 'w') as f:
                f.write(content)
            print(f"  ✅ Applied path fixes")
        else:
            print(f"  ℹ️  No changes needed")

def create_path_helper_scripts(deployed_dir):
    """Create helper scripts for path resolution"""
    
    # Create a config loader script
    config_loader = '''#!/bin/bash
# config_loader.sh - Load LLM Commander configuration
# This should be sourced by other scripts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$LLMC_ROOT/llmc.toml"

# Export config path for other scripts
export LLMC_CONFIG="$CONFIG_FILE"
export LLMC_ROOT="$LLMC_ROOT"

# Source the config if it exists
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE" 2>/dev/null || true
fi

# Set default values if not configured
export CLAUDE_API_KEY="${CLAUDE_API_KEY:-}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
'''
    
    # Create tool finder script  
    tool_finder = '''#!/bin/bash
# tool_finder.sh - Find tools and scripts from anywhere in llmc/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export LLMC_ROOT="$LLMC_ROOT"
export LLMC_TOOLS="$LLMC_ROOT/tools"
export LLMC_SCRIPTS="$LLMC_ROOT/scripts"

# Helper functions
find_tool() {
    local tool_name="$1"
    if [ -f "$LLMC_TOOLS/$tool_name" ]; then
        echo "$LLMC_TOOLS/$tool_name"
    else
        echo "$LLMC_SCRIPTS/$tool_name" 2>/dev/null || echo ""
    fi
}
'''
    
    # Write helper scripts
    scripts_dir = deployed_dir / 'scripts'
    with open(scripts_dir / 'config_loader.sh', 'w') as f:
        f.write(config_loader)
    
    with open(scripts_dir / 'tool_finder.sh', 'w') as f:
        f.write(tool_finder)
    
    # Make them executable
    os.chmod(scripts_dir / 'config_loader.sh', 0o755)
    os.chmod(scripts_dir / 'tool_finder.sh', 0o755)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Deploy LLM Commander template with path fixes')
    parser.add_argument('target_dir', help='Target directory to deploy to')
    parser.add_argument('--template-dir', default='llmc_template', help='Template directory to deploy from')
    parser.add_argument('--create-helpers', action='store_true', help='Create path helper scripts')
    
    args = parser.parse_args()
    
    target_path = Path(args.target_dir)
    template_path = Path(args.template_dir)
    
    # Deploy template
    print(f"🚀 Deploying template from {template_path} to {target_path}")
    
    # Create llmc directory in target
    llmc_dir = target_path / 'llmc'
    llmc_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy all template files
    shutil.copytree(template_path, llmc_dir, dirs_exist_ok=True)
    print(f"✅ Deployed template to {llmc_dir}")
    
    # Fix paths in deployed scripts
    fix_script_paths(llmc_dir)
    
    # Create helper scripts if requested
    if args.create_helpers:
        create_path_helper_scripts(llmc_dir)
    
    print(f"🎉 Deployment complete! LLM Commander is now available in {llmc_dir}")
    print(f"📝 Test with: cd {target_path} && ./llmc/scripts/claude_wrap.sh 'Hello world'")
'''
    
    return deploy_content

if __name__ == '__main__':
    deploy_content = create_fixed_deploy_py()
    with open('deploy_with_path_fixes.py', 'w') as f:
        f.write(deploy_content)
    print("✅ Created deploy_with_path_fixes.py")
    print("Usage: python3 deploy_with_path_fixes.py ~/src/githubblog")