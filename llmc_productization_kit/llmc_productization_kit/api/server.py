from __future__ import annotations

import os
from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path

# Import the local package (installed from tools/rag)
from rag.search import search_spans
from rag.cli import cli as rag_cli  # reuse implementation if needed

app = FastAPI(title="LLMC RAG API", version="0.1.0")

class IndexRequest(BaseModel):
    since: Optional[str] = None
    no_export: bool = False

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/index")
def index(req: IndexRequest):
    # Defer to the CLI implementation for consistency.
    # Doing this avoids duplicate logic; we just shell out the function via click.
    # NOTE: For large repos, you might prefer importing the indexer directly.
    from rag.indexer import index_repo
    stats = index_repo(since=req.since, export_json=not req.no_export)
    return {"message": "indexed", "stats": stats}

@app.get("/search")
def search(q: str = Query(..., description="Query string"),
           limit: int = Query(5, ge=1, le=50)):
    hits = search_spans(q, limit=limit)
    return {"count": len(hits), "results": [h.__dict__ for h in hits]}
