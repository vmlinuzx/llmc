# SDD — LLMC Repo Registration Tool (`llmc-rag-repo`)

## TL;DR

CLI-first tool that:

- Takes a repo path and gets it ready for LLMC’s RAG system.
- Detects or creates a self-contained RAG workspace folder inside the repo.
- Maintains a central repo registry shared with the RAG Daemon.
- Is idempotent and low-ceremony (safe to run many times).
