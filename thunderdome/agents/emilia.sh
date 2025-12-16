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
#   ./thunderdome/agents/emilia.sh                    # Test current repo
#   ./thunderdome/agents/emilia.sh --repo /path/to/x  # Test specific repo
#   ./thunderdome/agents/emilia.sh --quick            # Security + gap only
#   ./thunderdome/agents/emilia.sh --report           # Summary only
#
# Environment:
#   LLMC_TARGET_REPO   - Target repository to test (default: auto-detect)
#   EMILIA_PARALLEL    - Run demons in parallel (default: false)
#
# Reports:
#   Written to: <target_repo>/tests/REPORTS/current/
#   Previous run archived to: <target_repo>/tests/REPORTS/previous/
#
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THUNDERDOME_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source common library
source "$THUNDERDOME_ROOT/lib/common.sh"

DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M:%S)

# Demon registry - all available demons
declare -A DEMONS=(
    ["security"]="demons/rem_security.sh"
    ["testing"]="demons/rem_testing.sh"
    ["gap"]="demons/rem_gap.sh"
    ["mcp"]="demons/rem_mcp.sh"
    ["performance"]="demons/rem_performance.sh"
    ["chaos"]="demons/rem_chaos.sh"
    ["dependency"]="demons/rem_dependency.sh"
    ["documentation"]="demons/rem_documentation.sh"
    ["config"]="demons/rem_config.sh"
    ["concurrency"]="demons/rem_concurrency.sh"
    ["upgrade"]="demons/rem_upgrade.sh"
)

# Results storage
declare -A DEMON_STATUS
declare -A DEMON_P0_COUNT
declare -A DEMON_P1_COUNT
declare -A DEMON_OUTPUT_FILE

show_header() {
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║   👸 EMILIA - Testing Saint                                  ║"
    echo "║   Commander of the Testing Demon Army                        ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${CYAN}Date: $DATE $TIME${NC}"
    echo -e "${CYAN}Target: $TARGET_REPO${NC}"
    echo ""
}

run_demon() {
    local demon_key="$1"
    local demon_script="${DEMONS[$demon_key]}"
    local demon_path="$SCRIPT_DIR/$demon_script"
    
    # Check if demon exists
    if [[ ! -x "$demon_path" ]]; then
        log_warning "Demon not available: $demon_key ($demon_script)"
        DEMON_STATUS[$demon_key]="MISSING"
        return 1
    fi
    
    echo -e "${YELLOW}═══ Summoning: $demon_key ═══${NC}"
    
    local start_time
    start_time=$(date +%s)
    local output_file
    output_file=$(mktemp)
    
    # Run demon with target repo
    if "$demon_path" --repo "$TARGET_REPO" 2>&1 | tee "$output_file"; then
        DEMON_STATUS[$demon_key]="SUCCESS"
        log_success "$demon_key completed"
    else
        DEMON_STATUS[$demon_key]="FAILED"
        log_error "$demon_key failed"
    fi
    
    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # Parse results (look for P0/P1 counts in output)
    local p0_count
    local p1_count
    p0_count=$(grep -cE "P0|CRITICAL|Severity: Critical" "$output_file" 2>/dev/null || echo "0")
    p1_count=$(grep -cE "P1|HIGH|Severity: High" "$output_file" 2>/dev/null || echo "0")
    
    # Ensure they are integers
    [[ ! "$p0_count" =~ ^[0-9]+$ ]] && p0_count=0
    [[ ! "$p1_count" =~ ^[0-9]+$ ]] && p1_count=0
    
    DEMON_P0_COUNT[$demon_key]="$p0_count"
    DEMON_P1_COUNT[$demon_key]="$p1_count"
    DEMON_OUTPUT_FILE[$demon_key]="$output_file"
    
    echo "  Duration: ${duration}s | P0: $p0_count | P1: $p1_count"
    echo ""
}

generate_summary() {
    local report_file
    report_file=$(report_path "$TARGET_REPO" "emilia" "daily")
    
    cat > "$report_file" <<EOF
# Emilia Daily Report - $DATE

**Generated:** $TIME
**Repository:** $TARGET_REPO

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

cleanup_temp_files() {
    for output_file in "${DEMON_OUTPUT_FILE[@]}"; do
        rm -f "$output_file" 2>/dev/null || true
    done
}

# ==============================================================================
# Main
# ==============================================================================

main() {
    local mode="full"
    local explicit_repo=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --repo)
                shift
                explicit_repo="${1:-}"
                ;;
            --quick)
                mode="quick"
                ;;
            --report)
                mode="report"
                ;;
            --tmux)
                mode="tmux"
                ;;
            --help|-h)
                echo "Usage: emilia.sh [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --repo <path>   Target repository to test"
                echo "  --quick         Run only security + gap demons"
                echo "  --report        Generate summary from existing results"
                echo "  --tmux          Spawn all demons in parallel tmux windows"
                echo "  --help          Show this help"
                exit 0
                ;;
            *)
                err "Unknown option: $1"
                exit 1
                ;;
        esac
        shift
    done
    
    # Resolve target repo
    TARGET_REPO=$(resolve_target_repo "$explicit_repo")
    export TARGET_REPO
    
    if [[ ! -d "$TARGET_REPO" ]]; then
        err "Target repository does not exist: $TARGET_REPO"
        exit 1
    fi
    
    # Initialize report directories
    init_report_dirs "$TARGET_REPO"
    
    show_header
    
    if [[ "$mode" == "report" ]]; then
        echo "Report-only mode - generating summary..."
        generate_summary
        exit 0
    fi
    
    # Rotate reports (current -> previous)
    rotate_reports "$TARGET_REPO"
    
    if [[ "$mode" == "tmux" ]]; then
        echo -e "${CYAN}TMUX Mode: Spawning all demons in parallel...${NC}"
        local session_name="emilia_demons_$(date +%H%M%S)"
        
        # Create new tmux session with first demon
        local first_demon=""
        local first_script=""
        for demon_key in "${!DEMONS[@]}"; do
            first_demon="$demon_key"
            first_script="$SCRIPT_DIR/${DEMONS[$demon_key]}"
            break
        done
        
        tmux new-session -d -s "$session_name" -n "$first_demon" \
            "bash -c '$first_script --repo \"$TARGET_REPO\"; echo \"=== $first_demon COMPLETE ===\"; read'"
        
        # Add remaining demons as new windows
        for demon_key in "${!DEMONS[@]}"; do
            [[ "$demon_key" == "$first_demon" ]] && continue
            local demon_script="$SCRIPT_DIR/${DEMONS[$demon_key]}"
            [[ ! -x "$demon_script" ]] && continue
            tmux new-window -t "$session_name" -n "$demon_key" \
                "bash -c '$demon_script --repo \"$TARGET_REPO\"; echo \"=== $demon_key COMPLETE ===\"; read'"
        done
        
        echo -e "${GREEN}✓ Spawned demons in tmux session: $session_name${NC}"
        echo ""
        echo "Attach with:  tmux attach -t $session_name"
        echo "Kill with:    tmux kill-session -t $session_name"
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
    
    # Cleanup temp files
    cleanup_temp_files
    
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
