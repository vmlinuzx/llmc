#!/usr/bin/env bash
# llm_gateway.sh - Bash wrapper for llm_gateway.js (template)
cd "$(dirname "$0")"
exec node llm_gateway.js "$@"
