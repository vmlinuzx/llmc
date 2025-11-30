# SDD – RAG Doctor (Core Design)

## 1. Scope

Provide a read-only diagnostics layer for the RAG index with:
- A programmatic API: `run_rag_doctor(repo_path) -> dict`
- A log-friendly formatter: `format_rag_doctor_summary(result, repo_name) -> str`
- A CLI surface: `rag doctor`

No behavior changes to indexing/enrichment/embedding logic.

## 2. Data Model & Queries

Uses existing tables:

- `files(id, path, mtime, ...)`
- `spans(id, file_id, span_hash, ...)`
- `enrichments(span_hash, ...)`
- `embeddings(span_hash, profile, ...)`

Derived metrics:

- `files`: `SELECT COUNT(*) FROM files`
- `spans`: `SELECT COUNT(*) FROM spans`
- `enrichments`: `SELECT COUNT(*) FROM enrichments`
- `embeddings`: `SELECT COUNT(*) FROM embeddings`

- `pending_enrichments`:

  ```sql
  SELECT COUNT(*)
  FROM spans
  LEFT JOIN enrichments ON spans.span_hash = enrichments.span_hash
  WHERE enrichments.span_hash IS NULL;
  ```

- `pending_embeddings` (profile `default`):

  ```sql
  SELECT COUNT(*)
  FROM spans
  LEFT JOIN embeddings
    ON spans.span_hash = embeddings.span_hash
   AND embeddings.profile = 'default'
  WHERE embeddings.span_hash IS NULL;
  ```

- `orphan_enrichments`:

  ```sql
  SELECT COUNT(*)
  FROM enrichments
  LEFT JOIN spans ON spans.span_hash = enrichments.span_hash
  WHERE spans.span_hash IS NULL;
  ```

- `top_pending_files` (for verbose mode / CLI):

  ```sql
  SELECT files.path AS path, COUNT(*) AS pending_spans
  FROM spans
  JOIN files ON spans.file_id = files.id
  LEFT JOIN enrichments ON spans.span_hash = enrichments.span_hash
  WHERE enrichments.span_hash IS NULL
  GROUP BY files.id
  ORDER BY pending_spans DESC
  LIMIT 5;
  ```

## 3. API Shape

```python
def run_rag_doctor(repo_path: Path, verbose: bool = False) -> dict: ...
def format_rag_doctor_summary(result: dict, repo_name: str) -> str: ...
```

Return payload (JSON-friendly):

```json
{
  "status": "OK" | "EMPTY" | "NO_DB" | "WARN",
  "repo": "/abs/path",
  "db_path": "/abs/path/to/index.db",
  "timestamp": "2025-11-29T00:00:00Z",
  "stats": {
    "files": 12,
    "spans": 3456,
    "enrichments": 3300,
    "embeddings": 2800,
    "pending_enrichments": 156,
    "pending_embeddings": 656,
    "orphan_enrichments": 0
  },
  "top_pending_files": [
    {"path": "tools/rag/quality_check/__init__.py", "pending_spans": 12}
  ],
  "issues": [
    "156 spans are pending enrichment.",
    "656 spans are pending embeddings (profile 'default')."
  ]
}
```

`format_rag_doctor_summary()` condenses this into a single log line.

## 4. CLI Contract (`rag doctor`)

- Command: `rag doctor`
- Options:
  - `--json`: emit full JSON report.
  - `-v / --verbose`: include extra detail (top pending files) in human output.

Behavior:

- Exit code 0 when `status` ∈ {`OK`, `EMPTY`}
- Exit code 1 when `status` ∉ {`OK`, `EMPTY`} (e.g., `WARN`, `NO_DB`).

## 5. Service Integration

In `RAGService.process_repo`:

- After enrichment step, before embeddings step:

  ```python
  # RAG doctor: quick index/enrichment health snapshot
  from tools.rag.doctor import format_rag_doctor_summary, run_rag_doctor
  doctor_result = run_rag_doctor(repo)
  print(format_rag_doctor_summary(doctor_result, repo.name))
  ```

This gives you a per-cycle view of backlog health in the service logs.
