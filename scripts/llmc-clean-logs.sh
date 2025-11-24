#!/bin/bash
# llmc-clean-logs.sh - Wrapper script for LLMC log management
# Usage: ./llmc-clean-logs.sh [options]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_MANAGER="$SCRIPT_DIR/llmc_log_manager.py"
DEFAULT_LOG_DIR="$SCRIPT_DIR/../logs"
DEFAULT_MAX_SIZE="10MB"

show_help() {
    cat << EOF
LLMC Log Cleanup Script

Usage: $0 [options]

Options:
    -d, --dir DIR       Log directory (default: $DEFAULT_LOG_DIR)
    -s, --size SIZE     Max file size (default: $DEFAULT_MAX_SIZE)
    -c, --check         Only check log sizes, don't rotate
    -r, --rotate        Rotate oversized logs (default action)
    -q, --quiet         Suppress output
    -h, --help          Show this help

Examples:
    $0 --check                           # Check current logs
    $0 --rotate                          # Rotate logs
    $0 --rotate --size 5MB --quiet       # Quiet rotation
    $0 -d /custom/logs --check           # Check custom directory

EOF
}

# Default values
LOG_DIR="$DEFAULT_LOG_DIR"
MAX_SIZE="$DEFAULT_MAX_SIZE"
ACTION="rotate"
QUIET=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dir)
            LOG_DIR="$2"
            shift 2
            ;;
        -s|--size)
            MAX_SIZE="$2"
            shift 2
            ;;
        -c|--check)
            ACTION="check"
            shift
            ;;
        -r|--rotate)
            ACTION="rotate"
            shift
            ;;
        -q|--quiet)
            QUIET="--quiet"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            show_help
            exit 1
            ;;
    esac
done

# Check if log manager exists
if [[ ! -f "$LOG_MANAGER" ]]; then
    echo "Error: Log manager script not found: $LOG_MANAGER" >&2
    exit 1
fi

# Run log manager
if [[ "$ACTION" == "check" ]]; then
    python "$LOG_MANAGER" --check $QUIET "$LOG_DIR"
else
    python "$LOG_MANAGER" --rotate --max-size "$MAX_SIZE" $QUIET "$LOG_DIR"
fi