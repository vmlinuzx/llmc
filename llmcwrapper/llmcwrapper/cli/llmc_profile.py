# llmcwrapper/cli/llmc_profile.py
from __future__ import annotations
import argparse, os, json, copy, sys
from llmcwrapper.config import load_resolved_config, deep_merge, set_dotted

def main():
    ap = argparse.ArgumentParser(description="Show or set active profile.")
    sub = ap.add_subparsers(dest="cmd")

    sp_show = sub.add_parser("show", help="Show resolved config for a profile")
    sp_show.add_argument("--profile", default=os.environ.get("LLMC_PROFILE","daily"))

    sp_set = sub.add_parser("set", help="Print shell export for LLMC_PROFILE=<name>")
    sp_set.add_argument("name")

    args = ap.parse_args()

    if args.cmd == "set":
        print(f'export LLMC_PROFILE="{args.name}"')
        return

    # default to show
    cfg = load_resolved_config(profile=getattr(args, "profile", "daily"), mode="yolo")
    print(json.dumps(cfg, ensure_ascii=False, indent=2))
