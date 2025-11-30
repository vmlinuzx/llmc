# RAG Doctor – User Guide

## What It Does

`RAG doctor` is a quick health check for your local RAG index. It tells you:

- How many files and spans are indexed.
- How many spans are enriched and embedded.
- How many spans are still waiting for enrichment/embeddings.
- Whether there are any "orphan" enrichment rows with no backing span.

You get this both as a **CLI command** and as **log spam in the RAG service**.

## CLI Usage

From your repo root:

```bash
rag doctor
```

Example output:

```text
🧪 RAG doctor (llmc): files=42, spans=12345, enrichments=12000 (pending=345),
embeddings=11000 (pending=1345), orphans=0 | first_issue: 345 spans are pending enrichment.
```

Options:

- `--json` – emit a full JSON report (script / dashboard friendly).
- `-v / --verbose` – when not using `--json`, also print the top files with pending enrichments.

```bash
rag doctor --json | jq .
rag doctor -v
```

Exit codes:

- `0` when status is `OK` or `EMPTY`.
- `1` when status is `WARN` or `NO_DB`.

## Service Log Integration

When running `llmc-rag-service`, each cycle does:

1. Sync changed files.
2. Enrich pending spans.
3. **Run RAG doctor and log a summary.**
4. Generate embeddings.
5. Run quality check (if enabled).
6. Rebuild the RAG graph.

In the logs you’ll see something like:

```text
  🤖 Enriching with: backend=ollama, router=on, tier=7b
  ✅ Enriched pending spans with real LLM summaries
  🧪 RAG doctor (llmc): files=42, spans=12345, enrichments=12000 (pending=345), embeddings=11000 (pending=1345), orphans=0 | first_issue: 345 spans are pending enrichment.
  ✅ Generated embeddings (limit=100)
```

This gives you a quick mental model of "how backed up is the pipe" on every cycle.
