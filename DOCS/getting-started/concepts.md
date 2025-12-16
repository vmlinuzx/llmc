# Core Concepts

Understanding how LLMC thinks helps you get the most out of it.

## 1. Local-First Philosophy
LLMC is designed to run **entirely on your machine**.
- **Data Privacy**: Your code never leaves your network unless you explicitly configure a remote LLM provider.
- **Speed**: Local indexes mean millisecond-latency searches.
- **Cost**: By using local models for routine tasks (indexing, simple enrichment), you save token costs on massive codebases.

## 2. The Data Stack

LLMC organizes your code into a structured database, not just a bag of text.

### Files & Spans
Instead of indexing whole files, LLMC slices code into **Spans**.
- A **Span** is a logical unit: a function, a class, or a top-level block.
- This means search results point you to the *exact function* you need, not just the file it's in.

### Enrichment
Raw code is hard for LLMs to search semantically. **Enrichment** solves this.
- LLMC uses a background LLM (like Qwen or Llama) to write a summary for every span.
- When you search for "auth logic", you match the *summary* describing authentication, even if the function is named `check_k()`.

### The Graph
LLMC builds a dependency graph connecting definitions and usages.
- **Nodes**: Functions, Classes, Modules.
- **Edges**: `calls`, `imports`, `extends`.
This allows "GraphRAG" questions like: *"What breaks if I change this function?"*

## 3. Freshness Envelope
LLMC has "Trust Issues" (v0.7.0). It prioritizes **accuracy over availability**.

- **Fresh**: The index matches the file on disk. Safe to use.
- **Stale**: The file changed, but the index hasn't updated yet.
- **Rotten**: The index is wildly out of sync.

If you query a file that you just edited, LLMC might say: *"I can't answer from RAG because the index is stale. Read the file directly."* This prevents hallucinations based on old code.

## 4. The Daemon
The **RAG Daemon** is the background worker that keeps everything fresh.
- It watches for file changes.
- It schedules "Index", "Embed", and "Enrich" jobs.
- It manages concurrency to keep your system responsive.

## 5. Tool Envelope (TE)
The **Tool Envelope** is the protocol LLMC uses to talk to agents.
- It wraps results in structured JSON.
- It includes metadata like line numbers, file paths, and confidence scores.
- It allows tools to say "I failed safely" rather than crashing the agent.
