#!/usr/bin/env bash
set -euo pipefail
echo "[1] yolo dry-run"
llmc-yolo --dry-run || python3 -m llmcwrapper.cli.llmc_yolo --dry-run
echo "[2] rag dry-run"
llmc-rag --dry-run || python3 -m llmcwrapper.cli.llmc_rag --dry-run || python3 -m llmcwrapper.cli.llmc_rag --dry-run --force
echo "[3] doctor"
llmc-doctor || python3 -m llmcwrapper.cli.llmc_doctor
echo "[4] profile show"
llmc-profile show || python3 -m llmcwrapper.cli.llmc_profile show
