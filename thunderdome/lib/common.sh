#!/usr/bin/env bash
# ==============================================================================
# Thunderdome Common Library
# ==============================================================================
# Shared helpers for all Thunderdome agents
# Source this at the top of agent scripts:
#   source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"
# ==============================================================================

# Colors
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[0;33m'
export BLUE='\033[0;34m'
export PURPLE='\033[0;35m'
export CYAN='\033[0;36m'
export NC='\033[0m'  # No Color

# ==============================================================================
# Logging
# ==============================================================================

log_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

log_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

log_error() {
    echo -e "${RED}✗ $1${NC}"
}

log_header() {
    local title="$1"
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    printf "║ %-60s ║\n" "$title"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# ==============================================================================
# Repo Detection
# ==============================================================================

# Resolve the target repository root
# Priority: 1) --repo arg  2) LLMC_TARGET_REPO env  3) git root  4) pwd
resolve_target_repo() {
    local explicit_repo="${1:-}"
    
    # 1) Explicit --repo argument
    if [[ -n "$explicit_repo" && -d "$explicit_repo" ]]; then
        realpath "$explicit_repo"
        return 0
    fi
    
    # 2) Environment override
    if [[ -n "${LLMC_TARGET_REPO:-}" && -d "${LLMC_TARGET_REPO:-}" ]]; then
        realpath "$LLMC_TARGET_REPO"
        return 0
    fi
    
    # 3) Git repository root
    if command -v git &>/dev/null && git rev-parse --is-inside-work-tree &>/dev/null; then
        git rev-parse --show-toplevel 2>/dev/null
        return 0
    fi
    
    # 4) Fallback to current directory
    pwd
}

# Get repo snapshot info (branch, clean/dirty)
repo_snapshot() {
    local repo_root="$1"
    
    if command -v git &>/dev/null && git -C "$repo_root" rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
        local branch dirty
        branch="$(git -C "$repo_root" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
        if git -C "$repo_root" diff --quiet --ignore-submodules HEAD &>/dev/null 2>&1; then
            dirty="clean"
        else
            dirty="dirty"
        fi
        printf 'Repo: %s\nBranch: %s (%s)\n' "$repo_root" "$branch" "$dirty"
    else
        printf 'Repo: %s (not a git repo)\n' "$repo_root"
    fi
}

# ==============================================================================
# Report Management
# ==============================================================================

# Standard report directories under the target repo
REPORTS_CURRENT="tests/REPORTS/current"
REPORTS_PREVIOUS="tests/REPORTS/previous"

# Initialize report directories for a target repo
init_report_dirs() {
    local repo_root="$1"
    mkdir -p "$repo_root/$REPORTS_CURRENT"
    mkdir -p "$repo_root/$REPORTS_PREVIOUS"
}

# Rotate reports: current -> previous (clears previous first)
rotate_reports() {
    local repo_root="$1"
    local current_dir="$repo_root/$REPORTS_CURRENT"
    local previous_dir="$repo_root/$REPORTS_PREVIOUS"
    
    # Only rotate if there's something in current
    if [[ -d "$current_dir" ]] && [[ -n "$(ls -A "$current_dir" 2>/dev/null)" ]]; then
        log_info "Rotating reports: current -> previous"
        
        # Clear previous
        rm -rf "${previous_dir:?}"/*
        
        # Move current to previous
        mv "$current_dir"/* "$previous_dir"/ 2>/dev/null || true
        
        log_success "Reports rotated"
    fi
}

# Generate standardized report filename
# Usage: report_filename <agent> <scope>
# Example: report_filename "emilia" "daily" -> emilia_daily_2025-12-16.md
report_filename() {
    local agent="$1"
    local scope="$2"
    local date
    date=$(date +%Y-%m-%d)
    echo "${agent}_${scope}_${date}.md"
}

# Get full path for a new report file
# Usage: report_path <repo_root> <agent> <scope>
report_path() {
    local repo_root="$1"
    local agent="$2"
    local scope="$3"
    echo "$repo_root/$REPORTS_CURRENT/$(report_filename "$agent" "$scope")"
}

# ==============================================================================
# Utility
# ==============================================================================

have_cmd() {
    command -v "$1" &>/dev/null
}

err() {
    local script_name
    script_name="$(basename "${BASH_SOURCE[1]:-thunderdome}")"
    printf '%s: %s\n' "$script_name" "$*" >&2
}
