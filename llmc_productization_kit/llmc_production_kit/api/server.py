from __future__ import annotations

import os
import json
import subprocess
from typing import List, Optional

from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel

app = FastAPI(title="LLMC RAG API", version="0.2.0")

# Try direct imports first, then fall back to CLI invocations.
def _have_rag_imports() -> bool:
    try:
        import rag  # noqa: F401
        return True
    except Exception:
        return False

def _cli(cmd: List[str]) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"CLI error: {e.stderr or e.stdout}")

class IndexRequest(BaseModel):
    since: Optional[str] = None
    no_export: bool = False

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/index")
def index(req: IndexRequest):
    if _have_rag_imports():
        try:
            from rag.indexer import index_repo  # type: ignore
            stats = index_repo(since=req.since, export_json=not req.no_export)
            return {"message": "indexed", "stats": stats}
        except Exception as e:
            # fall back to CLI if import path present but failed at runtime
            pass
    # Fallback to CLI
    cmd = ["rag", "index"]
    if req.since:
        cmd += ["--since", req.since]
    out = _cli(cmd)
    return {"message": "indexed (via cli)", "stdout": out}

@app.get("/search")
def search(q: str = Query(..., description="Query string"),
           limit: int = Query(5, ge=1, le=50)):
    if _have_rag_imports():
        try:
            from rag.search import search_spans  # type: ignore
            hits = search_spans(q, limit=limit)
            # attempt to serialize hits
            def _ser(h):
                try:
                    return h.__dict__
                except Exception:
                    return h
            return {"count": len(hits), "results": [_ser(h) for h in hits]}
        except Exception:
            pass
    # Fallback to CLI
    out = _cli(["rag", "search", q, "--limit", str(limit)])
    # try to parse json, else return raw text
    try:
        data = json.loads(out)
        return {"count": len(data) if isinstance(data, list) else 0, "results": data}
    except Exception:
        return {"count": None, "results_text": out}
