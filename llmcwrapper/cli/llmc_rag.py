# llmcwrapper/cli/llmc_rag.py
from __future__ import annotations
import argparse, os, json
from llmcwrapper.adapter import send

def main():
    ap = argparse.ArgumentParser(description="LLMC RAG mode (RAG/tools enabled).")
    ap.add_argument("--profile", default=os.environ.get("LLMC_PROFILE","daily"))
    ap.add_argument("--overlay", action="append", default=[])
    ap.add_argument("--set", dest="sets", action="append", default=[])
    ap.add_argument("--unset", dest="unsets", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--model", default=None)
    ap.add_argument("--shadow-profile", default=None, help="Run a parallel dry-run under another profile and log telemetry")
    args = ap.parse_args()

    out = send(messages=[{"role":"user","content":"ping"}],
               tools=[{"type":"rag","name":"default"}],
               model=args.model,
               mode="rag",
               profile=args.profile,
               overlays=args.overlay,
               sets=args.sets,
               unsets=args.unsets,
               force=args.force,
               dry_run=args.dry_run)
    print(json.dumps(out, ensure_ascii=False))

    if args.shadow_profile:
        send(messages=[{"role":"user","content":"ping (shadow)"}],
             tools=[{"type":"rag","name":"default"}],
             model=None,
             mode="rag",
             profile=args.shadow_profile,
             overlays=args.overlay,
             sets=args.sets,
             unsets=args.unsets,
             force=True,
             dry_run=True)
