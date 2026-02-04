# llmc debug

The `llmc debug` command group provides low-level diagnostics, manual workflow triggers, and troubleshooting tools. It is the primary interface for managing the RAG index and pipeline manually.

## Commands

### `doctor`

Diagnose RAG health, configuration validity, and workspace integrity.

```bash
llmc debug doctor --json
```

### `index`

Run the indexing process. Scans the repository and updates the file index.

```bash
llmc debug index
```

### `sync`

Incrementally update spans for changed files.

```bash
llmc debug sync --since HEAD~1
```

### `embed`

Calculate embeddings for spans that need them.

```bash
llmc debug embed
```

### `enrich`

Run enrichment tasks (summarization, tagging) on spans.

```bash
llmc debug enrich
```

### `graph`

Build or rebuild the schema graph for the repository.

```bash
llmc debug graph
```

### `plan`

Generate a retrieval plan for a query without executing it.

```bash
llmc debug plan "how does authentication work"
```

### `inspect`

Deep dive into a file or symbol to see its internal state, spans, and metadata.

```bash
llmc debug inspect --path llmc/rag/pipeline.py
```

### `export`

Export the entire RAG workspace to a tarball for backup or debugging.

```bash
llmc debug export --output backup.tar.gz
```

### `file-descriptions`

Generate stable file-level descriptions for use in `mcgrep` and LLM context.

```bash
llmc debug file-descriptions
```
