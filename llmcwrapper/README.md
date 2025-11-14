# llmcwrapper

A small, unixy product: two stable entrypoints on top of a shared adapter—no more brittle shell flags.

- `llmc-yolo` — fast lane (no RAG/tools).
- `llmc-rag` — retrieval/tools lane (RAG on, tools allowed).
- `llmc-doctor` — health/config checks.
- `llmc-profile` — show/set active profiles and diffs.

## Install (editable)

```bash
pip install -e .
```

## Quick start

```bash
# dry runs (no provider calls)
llmc-yolo --dry-run
llmc-rag  --dry-run || llmc-rag --dry-run --force

# overrides
llmc-rag --set profiles.daily.temperature=0.1
LLMC_SET='profiles.daily.model="sonnet-3.7"' llmc-rag --dry-run

# doctor & profile
llmc-doctor
llmc-profile show --profile daily
llmc-profile set yolo
```
