from __future__ import annotations

import json
import subprocess
import os
from typing import List, Optional

from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel

app = FastAPI(title="LLMC RAG API", version="0.3.1")


def _apply_toml_to_env() -> None:
    """Load llmc.toml (if present) and map keys to env vars expected by engines.
    ENV wins over TOML; don't clobber existing values.
    """
    path = "llmc.toml"
    if not os.path.exists(path):
        return
    try:
        import tomllib  # Python 3.11+
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
    except Exception:
        return

    # Map TOML keys to environment variables consumed by tools/rag/config.py
    mappings = {
        ("embeddings", "preset"): "EMBEDDINGS_MODEL_PRESET",
        ("embeddings", "model"): "EMBEDDINGS_MODEL_NAME",
        ("storage", "index_path"): "LLMC_RAG_INDEX_PATH",
        ("enrichment", "enabled"): "ENRICHMENT_ENABLED",
        ("enrichment", "model"): "ENRICHMENT_MODEL",
        ("enrichment", "batch_size"): "ENRICHMENT_BATCH_SIZE",
    }
    for (section, key), env_name in mappings.items():
        if env_name in os.environ:
            continue
        val = cfg.get(section, {}).get(key)
        if val is None:
            continue
        if isinstance(val, bool):
            os.environ[env_name] = "1" if val else "0"
        else:
            os.environ[env_name] = str(val)


# Apply at import-time for typical server usage
_apply_toml_to_env()


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
    # Also apply per-request to allow hot-reload of TOML without restart
    _apply_toml_to_env()
    if _have_rag_imports():
        try:
            from rag.indexer import index_repo  # type: ignore
            stats = index_repo(since=req.since, export_json=not req.no_export)
            return {"message": "indexed", "stats": stats}
        except Exception:
            pass
    # Fallback to CLI
    cmd = ["rag", "index"]
    if req.since:
        cmd += ["--since", req.since]
    if req.no_export:
        cmd += ["--no-export"]
    out = _cli(cmd)
    return {"message": "indexed (via cli)", "stdout": out}


@app.get("/search")
def search(
    q: str = Query(..., description="Query string"),
    limit: int = Query(5, ge=1, le=50),
):
    _apply_toml_to_env()
    if _have_rag_imports():
        try:
            from rag.search import search_spans  # type: ignore
            hits = search_spans(q, limit=limit)

            def _ser(h):
                try:
                    return h.__dict__
                except Exception:
                    return h

            return {"count": len(hits), "results": [_ser(h) for h in hits]}
        except Exception:
            pass
    # Fallback to CLI with JSON
    out = _cli(["rag", "search", q, "--limit", str(limit), "--json"])
    try:
        data = json.loads(out)
        return {"count": len(data) if isinstance(data, list) else 0, "results": data}
    except Exception:
        return {"count": None, "results_text": out}

