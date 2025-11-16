# SDD — LLMC RAG Daemon (`llmc-rag-daemon`)

## TL;DR

Long-running background service that:

- Owns all scheduled RAG refresh work for registered repos.
- Reads a central repo registry, decides what needs work, and runs jobs with bounded concurrency.
- Persists minimal, durable state per repo (last run, status, failures, backoff).
- Exposes a tiny control surface so CLIs/tools can ask for status or nudge refresh.
- Runs as a single-process, multi-worker daemon that can later grow HTTP/Unix-socket control.

This SDD defines behavior and boundaries; concrete module layout lives in the Implementation SDD.
