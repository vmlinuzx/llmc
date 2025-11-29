"""CLI entry point for `llmc-rag`."""

from __future__ import annotations

import argparse
import json
import os
import sys

from llmcwrapper.adapter import AdapterError, send


def main() -> int:
    """Run the LLMC RAG-mode CLI."""
    ap = argparse.ArgumentParser(description="LLMC RAG mode (RAG/tools enabled).")
    ap.add_argument("--profile", default=os.environ.get("LLMC_PROFILE", "daily"))
    ap.add_argument("--overlay", action="append", default=[])
    ap.add_argument("--set", dest="sets", action="append", default=[])
    ap.add_argument("--unset", dest="unsets", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--model", default=None)
    ap.add_argument("--shadow-profile",
        default=None,
        help="Run a parallel dry-run under another profile and log telemetry",
    )
    ap.add_argument("query", nargs="*", help="User query string (optional, defaults to 'ping')")
    args = ap.parse_args()

    user_query = " ".join(args.query) if args.query else "ping"

    try:
        out = send(
            messages=[{"role": "user", "content": user_query}],
            tools=[{"type": "rag", "name": "default"}],
            model=args.model,
            mode="rag",
            profile=args.profile,
            overlays=args.overlay,
            sets=args.sets,
            unsets=args.unsets,
            force=args.force,
            dry_run=args.dry_run,
        )
    except AdapterError as exc:
        print(f"llmc-rag: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(out, ensure_ascii=False))

    if args.shadow_profile:
        try:
            send(
                messages=[{"role": "user", "content": "ping (shadow)"}],
                tools=[{"type": "rag", "name": "default"}],
                model=None,
                mode="rag",
                profile=args.shadow_profile,
                overlays=args.overlay,
                sets=args.sets,
                unsets=args.unsets,
                force=True,
                dry_run=True,
            )
        except AdapterError as exc:
            # Shadow profile is best-effort; report but keep primary result.
            print(f"llmc-rag (shadow): {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
