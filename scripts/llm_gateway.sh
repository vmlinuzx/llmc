#!/usr/bin/env bash
# llm_gateway.sh - Bash wrapper for llm_gateway.js
cd "$(dirname "$0")"
node llm_gateway.js "$@"