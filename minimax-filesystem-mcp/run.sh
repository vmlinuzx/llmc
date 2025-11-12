#!/bin/sh
# STDIO mode startup script for MiniMax filesystem MCP server
set -e

# Change to script directory
cd "$(dirname "$0")"

# Check if Go is available, install if needed
if ! command -v go >/dev/null 2>&1; then
    echo "Go is not installed. Installing Go..." >&2
    
    # Install Go if not available
    if [ ! -d "/workspace/go" ]; then
        echo "Downloading and installing Go..." >&2
        curl -L https://go.dev/dl/go1.22.1.linux-amd64.tar.gz | tar -xz -C /workspace
    fi
    
    # Add Go to PATH
    export PATH=/workspace/go/bin:$PATH
fi

# Check if binary exists, build if not
if [ ! -f "mcp-filesystem-server" ]; then
    echo "Building MCP filesystem server..." >&2
    go mod tidy
    go build -o mcp-filesystem-server .
    echo "Build completed successfully" >&2
fi

# Create workspace directory if it doesn't exist
if [ ! -d "workspace" ]; then
    mkdir -p workspace
    echo "Created workspace directory" >&2
fi

# Start the MCP server with allowed directories
echo "Starting MiniMax filesystem MCP server..." >&2
./mcp-filesystem-server workspace