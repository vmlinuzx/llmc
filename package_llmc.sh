#!/bin/bash
# LLMC Textual TUI - Binary Packaging Script
# Creates a standalone executable using PyInstaller

set -e

echo "🚀 LLMC Binary Packaging Script"
echo "================================"

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "📦 Installing PyInstaller..."
    pip install pyinstaller
fi

# Create build directory
mkdir -p dist
echo "📁 Created dist/ directory"

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build/ dist/*.spec

# Create PyInstaller spec file
cat > llmc_tui.spec << 'EOF'
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['llmc_textual.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'textual.app',
        'textual.widgets',
        'textual.containers',
        'textual.binding',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='llmc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Hide console window on Windows
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path if you have one
)
EOF

echo "📝 Created PyInstaller spec file"

# Build the binary
echo "🔨 Building LLMC binary..."
pyinstaller llmc_tui.spec --clean --noconfirm

# Move to dist
echo "📦 Moving to dist/ directory..."
cp dist/llmc.exe dist/llmc 2>/dev/null || true

# Create distribution package
cd dist
echo "📦 Creating distribution package..."

# Create package directory
mkdir -p llmc-tui-v1.0
cp llmc llmc-tui-v1.0/
cp ../llmc_demo.py llmc-tui-v1.0/
cp ../README.md llmc-tui-v1.0/

# Create startup script
cat > llmc-tui-v1.0/llmc.sh << 'EOF'
#!/bin/bash
# LLMC Textual TUI Launcher
./llmc "$@"
EOF

chmod +x llmc-tui-v1.0/llmc.sh

# Create Windows batch file
cat > llmc-tui-v1.0/llmc.bat << 'EOF'
@echo off
llmc.exe
EOF

# Create README
cat > llmc-tui-v1.0/INSTALL.txt << 'EOF'
LLMC Textual TUI - Standalone Binary
====================================

QUICK START:
- Linux/Mac: ./llmc or ./llmc.sh
- Windows: llmc.exe or llmc.bat

REQUIREMENTS:
- None! This is a standalone binary.

FEATURES:
- Single-key navigation (1,2,3,9)
- Professional terminal interface
- Smart Setup sub-menu
- No Python installation required

For support: Check the included documentation.
EOF

# Create zip package
zip -r llmc-tui-v1.0-standalone.zip llmc-tui-v1.0/

echo "✅ Packaging complete!"
echo ""
echo "📦 DISTRIBUTION FILES CREATED:"
echo "   • llmc-tui-v1.0/ (directory with binary + docs)"
echo "   • llmc-tui-v1.0-standalone.zip (ready to distribute)"
echo ""
echo "🎯 TO DISTRIBUTE:"
echo "   1. Share: llmc-tui-v1.0-standalone.zip"
echo "   2. Users unzip and run ./llmc"
echo "   3. No installation needed!"

cd ..
echo ""
echo "🎉 LLMC binary packaging complete!"
echo "🚀 Ready to ship your badass TUI to the world!"