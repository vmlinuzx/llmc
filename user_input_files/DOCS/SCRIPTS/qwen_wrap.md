# Qwen Integration for LLM Commander

This directory contains the `qwen_wrap.sh` script and configuration for integrating with Qwen models through LLM Commander's orchestration layer.

## Overview

The Qwen wrapper extends LLM Commander's existing patterns to specifically handle Qwen models (both local and API). It provides:

- Context injection from contracts, agents, and research papers
- Smart routing between local Qwen models and Qwen APIs
- Chaos testing mode for adversarial analysis
- Cost optimization through local-first approach
- Integration with LLMC's semantic caching and logging

## Usage

```bash
# Basic usage with local Qwen model
./scripts/qwen_wrap.sh --local "Analyze this code for potential vulnerabilities"

# With API routing (if configured)
./scripts/qwen_wrap.sh --api "What are the latest developments in LLM safety?"

# Chaos testing mode
./scripts/qwen_wrap.sh --chaos "Generate adversarial inputs for the authentication system"

# Auto-routing based on task complexity
./scripts/qwen_wrap.sh "Review this research paper on chaos testing"
```

## Configuration

The system respects the following configuration sources in priority order:

1. Environment variables
2. `.qwen/config.toml` in the target repository
3. Default values in the script

### Environment Variables

- `QWEN_MODEL`: Local Qwen model to use (default: qwen2.5:30b-instruct-q4_K_M)
- `QWEN_API_MODEL`: Remote Qwen model name
- `QWEN_APPROVAL`: Approval policy override
- `QWEN_WRAP_ENABLE_LOGGING`: Enable/disable logging (default: 1)
- `QWEN_WRAP_DEBUG`: Enable debug output

### Research Context

The wrapper can automatically include research paper context from `DOCS/RESEARCH/` when detected in the prompt. Set `INCLUDE_RESEARCH=1` to force research context inclusion.

## Features

- **Smart Context Loading**: Automatically includes CONTRACTS.md and AGENTS.md when relevant
- **RAG Database Integration**: Leverages the .rag/index_v2.db for sophisticated context retrieval
- **Research Paper Awareness**: Can search and analyze research papers stored in DOCS/RESEARCH/
- **Token Economy**: Reuses semantic cache to minimize model calls for similar queries
- **Sandbox Protection**: Runs with safety constraints and repo-specific boundaries
- **Logging & Tracking**: Full logging of Qwen interactions with timestamps and exit status
- **Chaos Mode**: Specialized routing for adversarial testing and security analysis

## Integration with LLM Commander

This wrapper follows the same patterns as `codex_wrap.sh`:
- Uses the same RAG system for context injection
- Integrates with the semantic cache
- Follows the same approval and safety patterns
- Maintains changelog entries for Qwen interactions
- Supports the same tool health and monitoring systems