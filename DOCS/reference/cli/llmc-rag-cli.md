# llmc-rag-cli Reference

Generated from `tools.rag.cli --help`

```text
Usage: python -m tools.rag.cli [OPTIONS] COMMAND [ARGS]...

  RAG ingestion CLI

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  benchmark     Run a lightweight embedding quality benchmark.
  doctor        Run RAG database health checks and diagnostics.
  embed         Preview or execute embedding jobs for spans.
  enrich        Preview or execute enrichment tasks (summary/tags) for...
  export        Export all RAG data to tar.gz archive.
  graph         Build a schema graph for the current repository.
  index         Index the repository (full or incremental).
  inspect       Fast inspection of a file or symbol with graph +...
  nav           Navigation tools over graph/fallback with freshness...
  paths         Show index storage paths.
  plan          Generate a heuristic retrieval plan for a natural...
  routing       Routing tools and evaluation.
  search        Run a cosine-similarity search over the local embedding...
  show-weights  Show configured path weights and priorities.
  stats         Print summary stats for the current index.
  sync          Incrementally update spans for selected files.
```
