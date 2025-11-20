#!/bin/bash
# Quick launcher for LLMC TUI
cd "$(dirname "$0")"
export PYTHONPATH="$PWD"
python3 -m llmc.tui.app "$@"
