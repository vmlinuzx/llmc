# Implementation SDD — LLMC RAG Daemon (`llmc-rag-daemon`)

## TL;DR

Implement `llmc-rag-daemon` as a single Python process with:

- Config loader + registry client.
- Tick-based scheduler loop.
- Worker pool invoking an existing RAG job runner CLI/module.
- File-based state store (JSON) behind an adapter.
- v1 control surface using flag files, plus a thin CLI wrapper (`llmc-rag`).
