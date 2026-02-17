<div align="center">

  # LLMC: LLM Client Research Lab

  **Making models smarter through client-side innovation.**
  <br>
  A research testbed for exploring techniques that enhance LLM performance without touching model weights.

  [![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
  [![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

## What is LLMC?

LLMC is a **learning testbed** for researching and experimenting with client-side techniques that make LLMs smarter, faster, and more capable—without retraining or fine-tuning.

The core thesis: **What happens between your code and the model matters as much as the model itself.**

### Research Areas

| Area | What We're Exploring |
|------|---------------------|
| **RLM (Recursive Language Models)** | Agentic sub-calls for 80-90% context reduction while maintaining reasoning depth |
| **Intelligent Routing** | Cascading from cheap local models → cloud fallbacks based on task complexity |
| **Context Engineering** | What to send, how to pack it, when to truncate |
| **Tool Orchestration** | MCP server patterns, security policies, egress controls |
| **Code Navigation** | AST-based indexing vs semantic search—when each wins |

---

## Current Focus: RLM

The flagship experiment is **Recursive Language Models**—using agentic sub-calls to navigate and analyze codebases instead of stuffing context windows.

```bash
# Deep analysis with 80-90% fewer tokens than reading files directly
llmc-cli rlm query "Trace the auth flow from API to database" --file auth.py

# Via MCP tool
{
  "name": "rlm_query",
  "arguments": {
    "task": "Why is this causing a race condition?",
    "path": "session_manager.py"
  }
}
```

**Why it works:** Instead of semantic similarity (RAG), RLM actually *reads*, *navigates*, and *reasons*. It follows imports, understands call graphs, and returns synthesized answers.

---

## Quick Start

```bash
# Install
pip install -e ".[rag,mcp]"

# Index a repo
llmc-cli repo register /path/to/project

# Run an RLM query
llmc-cli rlm query "Explain the core architecture" --budget 0.50
```

---

## Project Structure

```
llmc/
├── rlm/           # Recursive Language Model engine
├── rag/           # Legacy RAG system (still useful for docs)
├── llmc_mcp/      # MCP server and tools
├── scripts/       # Utilities and benchmarks
├── tests/         # Test suite
└── DOCS/          # Documentation
```

---

## Philosophy

This is a **learning environment**, not a production framework. Expect:

- Experiments that get abandoned
- Breaking changes when we find better approaches  
- Code that prioritizes understanding over polish
- Documentation that explains *why* not just *how*

The goal is discovery, not stability.

---

## History

Created by David Carroll after burning through API limits too fast and asking: *"What if the client was smarter?"*

---

_Current experiments: RLM v1.0, MCP Hospital-Grade Security, Dialectical Testing_
