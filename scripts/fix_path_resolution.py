#!/usr/bin/env python3
"""
Fix path resolution for deployed LLM Commander template.
This script updates all scripts to work correctly from their new llmc/ subdirectory location.
"""

import os
import re
import sys
from pathlib import Path

def fix_shell_scripts(template_dir):
    """Fix shell script path references"""
    
    # Common path replacements that need to be fixed
    path_fixes = [
        # When script is in llmc/scripts/, these should point to the parent llmc/
        (r'source \.\./', 'source ../../'),
        (r'\.\./tools/', '../../tools/'),
        (r'\.\./config/', '../../config/'),
        (r'\.\./scripts/', '../../scripts/'),
        
        # llmc.toml and other config files are now in parent directory
        ('llmc.toml', '../llmc.toml'),
        
        # Tools and scripts are now at different relative paths
        (r'tools/(?!\w)', '../../tools/'),
        (r'config/(?!\w)', '../../config/'),
        (r'scripts/(?!\w)', '../../scripts/'),
        
        # Fix cd commands that assume current directory
        (r'cd llmc', 'cd ..'),
        (r'cd \.\./', 'cd ../'),
    ]
    
    scripts_dir = Path(template_dir) / 'scripts'
    if not scripts_dir.exists():
        print(f"⚠️  Scripts directory not found: {scripts_dir}")
        return
    
    for script_file in scripts_dir.glob('*.sh'):
        print(f"🔧 Fixing paths in: {script_file}")
        
        with open(script_file, 'r') as f:
            content = f.read()
        
        original_content = content
        
        for pattern, replacement in path_fixes:
            content = re.sub(pattern, replacement, content)
        
        if content != original_content:
            with open(script_file, 'w') as f:
                f.write(content)
            print(f"  ✅ Updated {len(path_fixes)} path references")
        else:
            print(f"  ℹ️  No path fixes needed")

def fix_config_files(template_dir):
    """Fix configuration file references"""
    
    config_dir = Path(template_dir) / 'config'
    if not config_dir.exists():
        return
    
    # Update default.toml to reference correct paths
    default_toml = config_dir / 'default.toml'
    if default_toml.exists():
        with open(default_toml, 'r') as f:
            content = f.read()
        
        # Fix path references in config
        content = content.replace('llmc.toml', '../llmc.toml')
        
        with open(default_toml, 'w') as f:
            f.write(content)
        print("🔧 Fixed config paths in default.toml")

def fix_python_scripts(template_dir):
    """Fix Python script path references"""
    
    scripts_dir = Path(template_dir) / 'scripts'
    if not scripts_dir.exists():
        return
    
    for script_file in scripts_dir.glob('*.py'):
        with open(script_file, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Fix sys.path and path imports
        content = re.sub(r"sys\.path\.insert\(0, '\.\.'\)", "sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))", content)
        
        # Fix relative imports
        content = re.sub(r"from \.\.", "from ..", content)
        
        if content != original_content:
            with open(script_file, 'w') as f:
                f.write(content)
            print(f"🔧 Fixed Python paths in: {script_file}")

if __name__ == '__main__':
    template_dir = sys.argv[1] if len(sys.argv) > 1 else 'llmc_template'
    
    print(f"🚀 Fixing path resolution for template: {template_dir}")
    
    fix_shell_scripts(template_dir)
    fix_config_files(template_dir) 
    fix_python_scripts(template_dir)
    
    print("✅ Path resolution fixes complete!")