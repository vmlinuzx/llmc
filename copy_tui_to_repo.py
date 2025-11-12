#!/usr/bin/env python3
"""
Copy LLMC Textual TUI files to current directory
Simple script to help get the TUI into your repo root
"""

import os
import shutil
import sys

def copy_tui_files():
    """Copy the TUI files to current directory."""
    
    # Source and destination paths
    workspace_path = "/workspace"
    files_to_copy = [
        "llmc_textual.py",
        "llmc_demo.py", 
        "test_navigation.py"
    ]
    
    current_dir = os.getcwd()
    print(f"📂 Current directory: {current_dir}")
    print("🚀 Copying LLMC Textual TUI files...")
    
    copied_files = []
    
    for filename in files_to_copy:
        src = os.path.join(workspace_path, filename)
        dst = os.path.join(current_dir, filename)
        
        try:
            if os.path.exists(src):
                shutil.copy2(src, dst)
                # Make main TUI executable
                if filename == "llmc_textual.py":
                    os.chmod(dst, 0o755)
                    print(f"✅ Made {filename} executable")
                
                copied_files.append(filename)
                print(f"✅ Copied {filename} to {current_dir}")
            else:
                print(f"⚠️  Source file not found: {src}")
        except Exception as e:
            print(f"❌ Error copying {filename}: {e}")
    
    print(f"\n🎯 Summary: Copied {len(copied_files)} files")
    print("📋 Files in current directory:")
    for filename in files_to_copy:
        dst = os.path.join(current_dir, filename)
        if os.path.exists(dst):
            size = os.path.getsize(dst)
            print(f"   • {filename} ({size:,} bytes)")
    
    if copied_files:
        print(f"\n🚀 To run the TUI:")
        print(f"   pip install textual")
        print(f"   ./llmc_textual.py")
        
    return len(copied_files) > 0

if __name__ == "__main__":
    success = copy_tui_files()
    if success:
        print("\n✨ LLMC Textual TUI ready in your repo root!")
    else:
        print("\n❌ No files copied. Check the source path.")
    
    sys.exit(0 if success else 1)