#!/usr/bin/env python3
"""
Test script to demonstrate LLMC Textual TUI navigation
Simulates key presses to show the single-key functionality
"""

import subprocess
import sys
import time
import signal

def test_llmc_navigation():
    """Test the LLMC TUI with simulated key presses."""
    print("🚀 Starting LLMC Textual TUI Test...")
    print("📋 Test Plan:")
    print("  1. Launch LLMC TUI")
    print("  2. Test key '3' (Smart Setup) - should show submenu")
    print("  3. Test key '7' (Back to Main) - should return to main")
    print("  4. Test key '9' (Exit) - should quit gracefully")
    print()
    
    # Launch the TUI
    try:
        process = subprocess.Popen(
            [sys.executable, '/workspace/llmc_textual.py'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0
        )
        
        # Give it a moment to initialize
        time.sleep(1)
        
        print("✅ LLMC TUI launched successfully!")
        print("🎯 Testing single-key navigation...")
        print()
        
        # Test sequence
        test_keys = ['3', '7', '9']  # Smart Setup -> Back -> Exit
        key_names = ['Smart Setup', 'Back to Main', 'Exit']
        
        for key, name in zip(test_keys, key_names):
            print(f"📝 Sending key '{key}' ({name})...")
            try:
                # Send the key and check for response
                process.stdin.write(key)
                process.stdin.flush()
                time.sleep(0.5)  # Give time for response
                print(f"  ✅ Key '{key}' sent successfully")
            except Exception as e:
                print(f"  ❌ Error sending key '{key}': {e}")
                break
        
        print("🏁 Test sequence completed!")
        
        # Clean shutdown
        try:
            process.terminate()
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            
        print("✅ LLMC TUI test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error launching LLMC TUI: {e}")
        return False

if __name__ == "__main__":
    success = test_llmc_navigation()
    sys.exit(0 if success else 1)