#!/usr/bin/env bash
# ==============================================================================
# EMILIA - Testing Saint / Orchestrator
# ==============================================================================
# 
# The commander of the Testing Demon Army.
# Schedules demons, triages findings, dispatches fixes, and reports results.
#
# Named after Emilia from Re:Zero - pure intentions, commands spirits.
#
# Usage:
#   ./tools/emilia_testing_saint.sh              # Full orchestration run
#   ./tools/emilia_testing_saint.sh --quick      # Just security + gap demons
#   ./tools/emilia_testing_saint.sh --report     # Generate summary only
#
# Environment:
#   LLMC_ROOT          - Repository root (default: current directory)
#   EMILIA_PARALLEL    - Run demons in parallel (default: false)
#   EMILIA_FIX         - Auto-dispatch fixer subagents (default: false)
#
# Output:
#   tests/REPORTS/emilia_daily_YYYY-MM-DD.md
#
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMC_ROOT="${LLMC_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
REPORTS_DIR="$LLMC_ROOT/tests/REPORTS"
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M:%S)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Demon registry
declare -A DEMONS=(
    ["security"]="rem_ruthless_security_agent.sh"
    ["testing"]="rem_ruthless_testing_agent.sh"
    ["gap"]="rem_ruthless_gap_agent.sh"
    ["mcp"]="ruthless_mcp_tester.sh"
)

# Results storage
declare -A DEMON_STATUS
declare -A DEMON_P0_COUNT
declare -A DEMON_P1_COUNT
declare -A DEMON_REPORT

log_header() {
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║   👸 EMILIA - Testing Saint                                  ║"
    echo "║   Commander of the Testing Demon Army                        ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${CYAN}Date: $DATE $TIME${NC}"
    echo -e "${CYAN}Repository: $LLMC_ROOT${NC}"
    echo ""
}

log_demon() {
    local demon_name="$1"
    echo -e "${YELLOW}═══ Summoning: $demon_name ═══${NC}"
}

log_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

log_error() {
    echo -e "${RED}✗ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

run_demon() {
    local demon_key="$1"
    local demon_script="${DEMONS[$demon_key]}"
    local demon_path="$SCRIPT_DIR/$demon_script"
    
    if [[ ! -x "$demon_path" ]]; then
        log_warning "Demon not found or not executable: $demon_script"
        DEMON_STATUS[$demon_key]="MISSING"
        return 1
    fi
    
    log_demon "$demon_key"
    
    local start_time=$(date +%s)
    local output_file=$(mktemp)
    
    # Run demon and capture output
    if "$demon_path" 2>&1 | tee "$output_file"; then
        DEMON_STATUS[$demon_key]="SUCCESS"
        log_success "$demon_key completed"
    else
        DEMON_STATUS[$demon_key]="FAILED"
        log_error "$demon_key failed"
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # Parse results (look for P0/P1 counts in output)
    local p0_count=$(grep -c "P0\|CRITICAL\|Severity: Critical" "$output_file" 2>/dev/null || echo "0")
    local p1_count=$(grep -c "P1\|HIGH\|Severity: High" "$output_file" 2>/dev/null || echo "0")
    
    DEMON_P0_COUNT[$demon_key]="$p0_count"
    DEMON_P1_COUNT[$demon_key]="$p1_count"
    DEMON_REPORT[$demon_key]="$output_file"
    
    echo "  Duration: ${duration}s | P0: $p0_count | P1: $p1_count"
    echo ""
}

generate_summary() {
    local report_file="$REPORTS_DIR/emilia_daily_$DATE.md"
    mkdir -p "$REPORTS_DIR"
    
    cat > "$report_file" << EOF
# Emilia Daily Report - $DATE

**Generated:** $TIME
**Repository:** $LLMC_ROOT

## Summary

| Demon | Status | P0 | P1 |
|-------|--------|----|----|
EOF

    local total_p0=0
    local total_p1=0
    
    for demon_key in "${!DEMON_STATUS[@]}"; do
        local status="${DEMON_STATUS[$demon_key]}"
        local p0="${DEMON_P0_COUNT[$demon_key]:-0}"
        local p1="${DEMON_P1_COUNT[$demon_key]:-0}"
        
        total_p0=$((total_p0 + p0))
        total_p1=$((total_p1 + p1))
        
        local status_emoji="✅"
        [[ "$status" == "FAILED" ]] && status_emoji="❌"
        [[ "$status" == "MISSING" ]] && status_emoji="⚠️"
        
        echo "| $demon_key | $status_emoji $status | $p0 | $p1 |" >> "$report_file"
    done
    
    echo "" >> "$report_file"
    echo "**Total Issues:** P0=$total_p0, P1=$total_p1" >> "$report_file"
    echo "" >> "$report_file"
    
    # Overall verdict
    if [[ $total_p0 -gt 0 ]]; then
        echo "## ❌ VERDICT: CRITICAL ISSUES FOUND" >> "$report_file"
        echo "" >> "$report_file"
        echo "Action required: Fix P0 issues before deployment." >> "$report_file"
    elif [[ $total_p1 -gt 0 ]]; then
        echo "## ⚠️ VERDICT: ISSUES FOUND" >> "$report_file"
        echo "" >> "$report_file"
        echo "Review P1 issues and address as time permits." >> "$report_file"
    else
        echo "## ✅ VERDICT: ALL CLEAR" >> "$report_file"
        echo "" >> "$report_file"
        echo "No critical issues found. Good to ship!" >> "$report_file"
    fi
    
    echo "" >> "$report_file"
    echo "---" >> "$report_file"
    echo "" >> "$report_file"
    echo "*Report generated by Emilia, the Testing Saint.*" >> "$report_file"
    
    log_success "Report saved to: $report_file"
    
    # Print summary to console
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${PURPLE}                         SUMMARY                               ${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  P0 Critical:  ${RED}$total_p0${NC}"
    echo -e "  P1 High:      ${YELLOW}$total_p1${NC}"
    echo ""
    
    if [[ $total_p0 -gt 0 ]]; then
        echo -e "${RED}❌ CRITICAL ISSUES FOUND - FIX BEFORE DEPLOYMENT${NC}"
    elif [[ $total_p1 -gt 0 ]]; then
        echo -e "${YELLOW}⚠️  Issues found - review when possible${NC}"
    else
        echo -e "${GREEN}✅ ALL CLEAR - Good to ship!${NC}"
    fi
    echo ""
}

# Main execution
main() {
    log_header
    
    local mode="full"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --quick)
                mode="quick"
                shift
                ;;
            --report)
                mode="report"
                shift
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    if [[ "$mode" == "report" ]]; then
        echo "Report-only mode - checking existing reports..."
        generate_summary
        exit 0
    fi
    
    echo -e "${CYAN}Mode: $mode${NC}"
    echo ""
    
    # Run demons based on mode
    if [[ "$mode" == "quick" ]]; then
        run_demon "security"
        run_demon "gap"
    else
        for demon_key in "${!DEMONS[@]}"; do
            run_demon "$demon_key"
        done
    fi
    
    # Generate summary report
    generate_summary
    
    # Exit with error if P0 issues found
    local total_p0=0
    for p0 in "${DEMON_P0_COUNT[@]}"; do
        total_p0=$((total_p0 + p0))
    done
    
    if [[ $total_p0 -gt 0 ]]; then
        exit 1
    fi
}

main "$@"
