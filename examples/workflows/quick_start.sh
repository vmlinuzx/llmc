#!/usr/bin/env bash
# Quick Start Workflow for LLMC Configuration
# Demonstrates the complete configuration setup process

set -euo pipefail

echo "🚀 LLMC Configuration Quick Start"
echo "=================================="

# Step 1: Check if configuration already exists
if [ -d "config" ] && [ -f "config/default.toml" ]; then
    echo "✅ Configuration already exists"
    echo ""
    echo "Current configuration:"
    if command -v python3 >/dev/null 2>&1; then
        python3 -m config.cli show --format plain
    else
        echo "  Install Python 3 to view configuration details"
    fi
else
    echo "📁 Initializing configuration..."
    
    # Step 2: Initialize configuration structure
    if command -v python3 >/dev/null 2>&1; then
        python3 -m config.cli init
    else
        echo "❌ Python 3 is required for configuration management"
        echo "Please install Python 3 and try again"
        exit 1
    fi
fi

echo ""
echo "🔧 Configuration Options:"
echo "========================"

# Step 3: Present configuration templates
echo "Choose a configuration template:"
echo ""
echo "1) Basic Local Development (Ollama)"
echo "2) Production Setup (Multiple APIs)"
echo "3) Cost-Optimized (Mixed Local/Remote)"
echo "4) Development/Debugging"
echo "5) Custom (edit local.toml manually)"
echo ""

read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        template="basic_local.toml"
        description="Local development with Ollama"
        ;;
    2)
        template="production.toml"
        description="Production setup with multiple APIs"
        ;;
    3)
        template="cost_optimized.toml"
        description="Cost-optimized with mixed local/remote"
        ;;
    4)
        template="development.toml"
        description="Development with maximum debugging"
        ;;
    5)
        echo "Opening local.toml for editing..."
        if command -v code >/dev/null 2>&1; then
            code config/local.toml
        elif command -v vim >/dev/null 2>&1; then
            vim config/local.toml
        elif command -v nano >/dev/null 2>&1; then
            nano config/local.toml
        else
            echo "Please edit config/local.toml manually with your preferred editor"
        fi
        template=""
        ;;
    *)
        echo "Invalid choice. Using basic local configuration."
        template="basic_local.toml"
        description="Basic local development"
        ;;
esac

# Step 4: Apply template if chosen
if [ -n "$template" ] && [ -f "examples/configs/$template" ]; then
    echo ""
    echo "📋 Applying $description configuration..."
    
    if [ -f "config/local.toml" ]; then
        read -p "local.toml already exists. Overwrite? (y/N): " overwrite
        if [ "$overwrite" != "y" ] && [ "$overwrite" != "Y" ]; then
            echo "Keeping existing local.toml"
        else
            cp "examples/configs/$template" "config/local.toml"
            echo "✅ Applied $template to config/local.toml"
        fi
    else
        cp "examples/configs/$template" "config/local.toml"
        echo "✅ Applied $template to config/local.toml"
    fi
fi

echo ""
echo "🔍 Configuration Validation"
echo "=========================="

# Step 5: Validate configuration
if command -v python3 >/dev/null 2>&1; then
    echo "Validating configuration..."
    if python3 -m config.cli validate; then
        echo "✅ Configuration is valid!"
    else
        echo "⚠️  Configuration has warnings or errors (see above)"
    fi
else
    echo "⚠️  Python 3 required for validation"
fi

echo ""
echo "🌍 Environment Check"
echo "==================="

# Step 6: Check environment setup
echo "Checking required environment setup..."

# Check for common provider environment variables
providers_found=0

if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo "✅ Claude API key configured"
    ((providers_found++))
fi

if [ -n "${AZURE_OPENAI_ENDPOINT:-}" ] && [ -n "${AZURE_OPENAI_KEY:-}" ]; then
    echo "✅ Azure OpenAI configured"
    ((providers_found++))
fi

if [ -n "${GOOGLE_API_KEY:-}" ]; then
    echo "✅ Google API key configured"
    ((providers_found++))
fi

if command -v ollama >/dev/null 2>&1; then
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "✅ Ollama service running"
        ((providers_found++))
    else
        echo "⚠️  Ollama installed but not running"
        echo "   Start with: ollama serve"
    fi
else
    echo "⚠️  Ollama not installed (optional)"
fi

if [ -n "${MINIMAXKEY2:-}" ]; then
    echo "✅ MiniMax API key configured"
    ((providers_found++))
fi

if [ $providers_found -eq 0 ]; then
    echo "⚠️  No LLM providers configured"
    echo "   Configure at least one provider:"
    echo "   - Claude: Set ANTHROPIC_API_KEY"
    echo "   - Azure: Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT"
    echo "   - Gemini: Set GOOGLE_API_KEY"
    echo "   - Ollama: Install and start Ollama service"
    echo "   - MiniMax: Set MINIMAXKEY2"
fi

echo ""
echo "🎯 Next Steps"
echo "============="

if [ $providers_found -gt 0 ]; then
    echo "1. Test your configuration:"
    echo "   python3 -m config.cli get providers.default"
    echo ""
    echo "2. Try LLMC with your configured provider:"
    echo "   ./scripts/claude_wrap.sh 'Hello, world!'"
    echo ""
    echo "3. Customize further by editing config/local.toml"
else
    echo "1. Configure at least one LLM provider (see environment check above)"
    echo "2. Test your configuration:"
    echo "   python3 -m config.cli get providers.default"
    echo ""
    echo "3. Try LLMC once providers are configured:"
    echo "   ./scripts/claude_wrap.sh 'Hello, world!'"
fi

echo ""
echo "4. Explore configuration options:"
echo "   python3 -m config.cli show"
echo "   python3 -m config.cli profiles --list"
echo ""
echo "📚 Documentation: config/README.md"
echo ""

# Step 7: Provide usage examples
echo "💡 Usage Examples"
echo "================="

cat <<'EOF'
# Show current configuration
python3 -m config.cli show

# Get specific values
python3 -m config.cli get storage.index_path
python3 -m config.cli get providers.default

# Update configuration
python3 -m config.cli set providers.default ollama --write

# Validate configuration
python3 -m config.cli validate --verbose

# List available provider profiles
python3 -m config.cli profiles --list

# Show profile details
python3 -m config.cli profiles --name claude

# Use with shell scripts (automatic environment export)
eval "$(python3 -m config.cli --export-shell)"
echo "Index path: $LLMC_STORAGE_INDEX_PATH"
echo "RAG enabled: $LLMC_RAG_ENABLED"
EOF

echo ""
echo "🎉 Configuration setup complete!"
echo "Happy coding with LLMC!"