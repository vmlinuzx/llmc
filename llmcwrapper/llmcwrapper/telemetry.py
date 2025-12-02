# llmcwrapper/telemetry.py
import json
import os
import time
import uuid


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p


def new_corr_id():
    return f"{int(time.time())}-{uuid.uuid4().hex[:8]}"


def log_event(base_dir, corr_id, kind, payload):
    runs = ensure_dir(os.path.join(base_dir, ".llmc", "runs"))
    # use corr_id as dir to group events of a run
    run_dir = ensure_dir(os.path.join(runs, corr_id))
    path = os.path.join(run_dir, "events.jsonl")
    rec = {"ts": int(time.time()), "corr_id": corr_id, "event": kind, **(payload or {})}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path
