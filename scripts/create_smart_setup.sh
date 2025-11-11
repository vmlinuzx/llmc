#!/usr/bin/env python3
"""
Create a smart setup.sh script that automatically configures
LLM Commander for both development and production deployments.
"""

def create_smart_setup():
    setup_content = '''#!/bin/bash
# setup.sh - Smart LLM Commander configuration for development and production
# Automatically detects deployment context and sets up paths correctly

set -euo pipefail

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}ℹ️  [$(date +'%H:%M:%S')]${NC} $1"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# Detect deployment context
detect_context() {
    # Find repo root using git, or fall back to current directory
    REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
    CURRENT_DIR=$(pwd)
    
    # Find LLM Commander root (current directory)
    LLMC_ROOT=$(pwd)
    
    # Detect if we're in production mode (llmc is subdirectory of repo)
    if [[ "$CURRENT_DIR" == *"/$REPO_ROOT/llmc" ]]; then
        DEPLOYMENT_MODE="production"
        LLMC_INSTALL_ROOT="$CURRENT_DIR"
    elif [[ "$REPO_ROOT" == "$LLMC_ROOT" ]]; then
        DEPLOYMENT_MODE="development"
        LLMC_INSTALL_ROOT="$CURRENT_DIR"
    else
        DEPLOYMENT_MODE="unknown"
        LLMC_INSTALL_ROOT="$CURRENT_DIR"
    fi
    
    log_info "Deployment Mode: $DEPLOYMENT_MODE"
    log_info "Repo Root: $REPO_ROOT"
    log_info "LLMC Root: $LLMC_ROOT"
    log_info "Install Root: $LLMC_INSTALL_ROOT"
}

# Set up environment variables
setup_environment() {
    # Core environment variables
    export REPO_ROOT="$REPO_ROOT"
    export LLMC_ROOT="$LLMC_ROOT"
    export LLMC_INSTALL_ROOT="$LLMC_INSTALL_ROOT"
    export DEPLOYMENT_MODE="$DEPLOYMENT_MODE"
    
    # Dynamic path resolution
    if [[ "$DEPLOYMENT_MODE" == "production" ]]; then
        # Production: llmc is subdirectory
        export LLMC_CONFIG_PATH="$LLMC_ROOT/../llmc.toml"
        export LLMC_TOOLS_PATH="$LLMC_ROOT/../tools"
        export LLMC_DOCS_PATH="$LLMC_ROOT/../docs"
    else
        # Development: everything at repo root
        export LLMC_CONFIG_PATH="$REPO_ROOT/llmc.toml"
        export LLMC_TOOLS_PATH="$REPO_ROOT/tools"
        export LLMC_DOCS_PATH="$REPO_ROOT/docs"
    fi
    
    # Create a config file that scripts can source
    cat > .llmc_env.sh << EOF
#!/bin/bash
# Auto-generated LLM Commander environment configuration

export REPO_ROOT="$REPO_ROOT"
export LLMC_ROOT="$LLMC_ROOT"  
export LLMC_INSTALL_ROOT="$LLMC_INSTALL_ROOT"
export DEPLOYMENT_MODE="$DEPLOYMENT_MODE"
export LLMC_CONFIG_PATH="$LLMC_CONFIG_PATH"
export LLMC_TOOLS_PATH="$LLMC_TOOLS_PATH"
export LLMC_DOCS_PATH="$LLMC_DOCS_PATH"

# Auto-detect API keys
export CLAUDE_API_KEY="${CLAUDE_API_KEY:-}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"

# Function to find tool paths dynamically
find_tool() {
    local tool_name="$1"
    local tool_path=""
    
    # Try scripts directory first
    if [[ -f "$LLMC_ROOT/scripts/$tool_name" ]]; then
        tool_path="$LLMC_ROOT/scripts/$tool_name"
    elif [[ -f "$LLMC_ROOT/tools/$tool_name" ]]; then
        tool_path="$LLMC_ROOT/tools/$tool_name"
    fi
    
    echo "$tool_path"
}
EOF
    
    log_success "Environment configuration created"
}

# Make all scripts executable
make_executable() {
    log_info "Making scripts executable..."
    
    # Make shell scripts executable
    find . -name "*.sh" -type f -exec chmod +x {} \\;
    
    # Make Python scripts with shebangs executable
    find . -name "*.py" -type f -exec grep -l "^#!/usr/bin/env python" {} \\; -exec chmod +x {} \\;
    
    # Make deploy script executable
    if [[ -f "deploy.py" ]]; then
        chmod +x deploy.py
    fi
    
    log_success "Scripts made executable"
}

# Update existing scripts with path resolution
update_scripts_with_paths() {
    log_info "Updating scripts with path resolution..."
    
    # Update shell scripts
    for script in scripts/*.sh; do
        if [[ -f "$script" ]]; then
            # Add path resolution at the start if not already present
            if ! grep -q ".llmc_env.sh" "$script"; then
                # Insert after shebang and comments
                awk '
                /^#!/{print; comment_seen=1; next}
                /^#/{if(comment_seen) print; next}
                !comment_seen{comment_seen=1; print; next}
                {print; exit}
                ' "$script" > "$script.tmp" && \\
                echo "# Source LLM Commander environment" >> "$script.tmp" && \\
                echo 'if [[ -f ".llmc_env.sh" ]]; then source ".llmc_env.sh"; fi' >> "$script.tmp" && \\
                echo "" >> "$script.tmp" && \\
                tail -n +2 "$script" >> "$script.tmp" && \\
                mv "$script.tmp" "$script"
                
                log_success "Added path resolution to $script"
            fi
        fi
    done
    
    # Update Python scripts
    for script in scripts/*.py; do
        if [[ -f "$script" ]]; then
            # Add path import if not already present
            if ! grep -q "import os" "$script"; then
                sed -i '1a import os' "$script"
            fi
            if ! grep -q "llmc_env" "$script"; then
                sed -i '2a # Auto-import environment' "$script" && \\
                sed -i '3a env_file = ".llmc_env.sh"' "$script" && \\
                sed -i '4a if os.path.exists(env_file):' "$script" && \\
                sed -i '5a     import subprocess' "$script" && \\
                sed -i '6a     subprocess.run(["bash", "-c", f"source {env_file} && export $(cat {env_file} | grep -v "^#" | cut -d= -f1)"], check=False)' "$script" && \\
                sed -i '7a ' "$script"
                
                log_success "Added environment loading to $script"
            fi
        fi
    done
}

# Create or copy configuration files
setup_configuration() {
    log_info "Setting up configuration..."
    
    # Copy local.example.toml to local.toml if it doesn't exist
    if [[ ! -f "config/local.toml" ]] && [[ -f "config/local.example.toml" ]]; then
        cp config/local.example.toml config/local.toml
        log_success "Created config/local.toml from template"
    fi
    
    # Ensure llmc.toml exists (it should from extraction)
    if [[ ! -f "llmc.toml" ]]; then
        log_warning "llmc.toml not found - you may need to copy it manually"
    else
        log_success "llmc.toml configuration found"
    fi
}

# Validate the setup
validate_setup() {
    log_info "Validating setup..."
    
    local errors=0
    
    # Check essential directories exist
    for dir in scripts tools config; do
        if [[ ! -d "$dir" ]]; then
            log_error "Missing required directory: $dir"
            ((errors++))
        fi
    done
    
    # Check environment file was created
    if [[ ! -f ".llmc_env.sh" ]]; then
        log_error "Environment file .llmc_env.sh was not created"
        ((errors++))
    else
        log_success "Environment file created"
    fi
    
    # Test that scripts can find config
    if source .llmc_env.sh && [[ -f "$LLMC_CONFIG_PATH" ]]; then
        log_success "Configuration path resolved correctly"
    else
        log_warning "Configuration path may not be correct"
    fi
    
    return $errors
}

# Show usage information
show_usage() {
    echo "LLM Commander Smart Setup"
    echo "Usage: ./setup.sh [options]"
    echo ""
    echo "Options:"
    echo "  --force    Force re-run even if already configured"
    echo "  --help     Show this help message"
    echo ""
    echo "This script will:"
    echo "  • Detect deployment context (development/production)"
    echo "  • Set up environment variables and paths"
    echo "  • Make scripts executable"
    echo "  • Add smart path resolution to existing scripts"
    echo "  • Configure local.toml if needed"
    echo "  • Validate the setup"
}

# Main execution
main() {
    local force=${1:-}
    
    # Show usage if requested
    if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
        show_usage
        exit 0
    fi
    
    # Skip if already configured and not forced
    if [[ -f ".setup_complete" ]] && [[ "$force" != "--force" ]]; then
        log_info "Setup already completed. Use --force to re-run."
        
        # Still try to load environment
        if [[ -f ".llmc_env.sh" ]]; then
            source .llmc_env.sh
            log_success "Environment loaded successfully"
        fi
        exit 0
    fi
    
    log_info "Starting LLM Commander smart setup..."
    
    # Run setup steps
    detect_context
    setup_environment
    make_executable
    update_scripts_with_paths
    setup_configuration
    
    # Validate setup
    if validate_setup; then
        # Mark setup as complete
        touch .setup_complete
        log_success "LLM Commander setup completed successfully!"
        echo ""
        echo "🎉 Ready to use! Try:"
        echo "  cd ~/src/githubblog"
        echo "  ./llmc/scripts/claude_wrap.sh 'Hello, world!'"
    else
        log_error "Setup completed with errors. Please review above."
        exit 1
    fi
}

# Run main function
main "$@"
'''
    
    return setup_content

if __name__ == '__main__':
    content = create_smart_setup()
    
    with open('/workspace/setup.sh', 'w') as f:
        f.write(content)
    
    print("✅ Created smart setup.sh script!")
    print("📋 Features:")
    print("  • Auto-detects development vs production mode")
    print("  • Sets up dynamic environment variables")
    print("  • Makes all scripts executable")
    print("  • Adds path resolution to existing scripts")
    print("  • Validates the setup")
    print("")
    print("🚀 Usage:")
    print("  cd llmc_template")
    print("  chmod +x setup.sh")
    print("  ./setup.sh")
    print("")
    print("Then deploy to githubblog:")
    print("  python3 deploy.py ~/src/githubblog")