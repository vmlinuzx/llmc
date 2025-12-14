#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# THUNDERDOME AGENT WRAPPER
# ═══════════════════════════════════════════════════════════════════════════
# Unified interface for invoking coding agents with automatic fallback.
# 
# Usage:
#   ./thunderdome_agent.sh "Your prompt here"
#   
# Environment Variables:
#   THUNDERDOME_BACKEND - Force backend: "gemini", "deepseek", or "auto" (default)
#   THUNDERDOME_TIMEOUT - Timeout in seconds (default: 600)
#   THUNDERDOME_LOG     - Log file path (default: /dev/null)
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# Configuration
BACKEND="${THUNDERDOME_BACKEND:-deepseek}"
TIMEOUT="${THUNDERDOME_TIMEOUT:-600}"
LOG="${THUNDERDOME_LOG:-/dev/null}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo "[$(date -Iseconds)] $1" >> "$LOG"
}

info() {
    echo -e "${BLUE}[THUNDERDOME]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[THUNDERDOME]${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[THUNDERDOME]${NC} $1" >&2
}

error() {
    echo -e "${RED}[THUNDERDOME]${NC} $1" >&2
}

# Check if Gemini CLI is available and has quota
check_gemini() {
    if ! command -v gemini &>/dev/null; then
        log "Gemini CLI not found"
        return 1
    fi
    
    # Quick test to see if quota is available
    # (gemini -y exits quickly if quota exhausted)
    if timeout 10 gemini -y "echo test" &>/dev/null; then
        return 0
    else
        log "Gemini quota check failed"
        return 1
    fi
}

# Check if Aider + DeepSeek is available
check_deepseek() {
    if ! command -v aider &>/dev/null; then
        log "Aider not found"
        return 1
    fi
    
    if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
        log "DEEPSEEK_API_KEY not set"
        return 1
    fi
    
    return 0
}

# Run with Gemini
run_gemini() {
    local prompt="$1"
    info "Invoking Gemini..."
    log "BACKEND: gemini"
    
    if timeout "$TIMEOUT" gemini -y "$prompt"; then
        success "Gemini completed successfully"
        log "RESULT: success"
        return 0
    else
        local exit_code=$?
        warn "Gemini failed with exit code: $exit_code"
        log "RESULT: failed ($exit_code)"
        return $exit_code
    fi
}

# Run with DeepSeek via Aider
run_deepseek() {
    local prompt="$1"
    info "Invoking DeepSeek via Aider..."
    log "BACKEND: deepseek"
    
    if timeout "$TIMEOUT" aider \
        --model deepseek/deepseek-chat \
        --no-auto-commits \
        --yes \
        --message "$prompt"; then
        success "DeepSeek completed successfully"
        log "RESULT: success"
        return 0
    else
        local exit_code=$?
        warn "DeepSeek failed with exit code: $exit_code"
        log "RESULT: failed ($exit_code)"
        return $exit_code
    fi
}

# Auto mode: try Gemini first, fall back to DeepSeek
run_auto() {
    local prompt="$1"
    
    # Try Gemini first if available
    if check_gemini; then
        info "Trying Gemini first..."
        if run_gemini "$prompt"; then
            return 0
        fi
        warn "Gemini failed, falling back to DeepSeek..."
        log "FALLBACK: gemini -> deepseek"
    else
        info "Gemini unavailable, using DeepSeek..."
    fi
    
    # Fall back to DeepSeek
    if check_deepseek; then
        if run_deepseek "$prompt"; then
            return 0
        fi
    else
        error "DeepSeek also unavailable!"
        return 1
    fi
    
    error "All backends failed!"
    return 1
}

# Main
main() {
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 \"prompt\""
        echo ""
        echo "Environment Variables:"
        echo "  THUNDERDOME_BACKEND  - Force backend: gemini, deepseek, auto (default)"
        echo "  THUNDERDOME_TIMEOUT  - Timeout in seconds (default: 600)"
        echo "  THUNDERDOME_LOG      - Log file path"
        exit 1
    fi
    
    local prompt="$1"
    log "═══════════════════════════════════════════════════════════════"
    log "THUNDERDOME AGENT INVOCATION"
    log "BACKEND_MODE: $BACKEND"
    log "TIMEOUT: ${TIMEOUT}s"
    log "PROMPT_LENGTH: ${#prompt} chars"
    log "═══════════════════════════════════════════════════════════════"
    
    case "$BACKEND" in
        gemini)
            run_gemini "$prompt"
            ;;
        deepseek)
            run_deepseek "$prompt"
            ;;
        auto)
            run_auto "$prompt"
            ;;
        *)
            error "Unknown backend: $BACKEND"
            exit 1
            ;;
    esac
}

main "$@"
