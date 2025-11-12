# llm_gateway.sh — Bash Wrapper

Path
- scripts/llm_gateway.sh

Purpose
- Convenience shim that invokes `node scripts/llm_gateway.js` with the same arguments.

Usage
- `./scripts/llm_gateway.sh [--local|--api|--claude|--azure-codex] [--repo PATH] [--azure-model NAME] "prompt"`
- Also supports stdin piping.

Notes
- All behavior is implemented in `llm_gateway.js`. See its reference page for flags and env.

