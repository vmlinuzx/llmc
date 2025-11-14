# llmcwrapper/cli/llmc_doctor.py
from __future__ import annotations
import argparse, os, json, socket, urllib.request
from llmcwrapper.config import load_resolved_config
from llmcwrapper.util import green, yellow, red, info

def _check_url(url: str) -> str:
    try:
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req, timeout=2)
        return green("OK")
    except Exception as e:
        return yellow(f"WARN ({e})")

def main():
    ap = argparse.ArgumentParser(description="LLMC doctor: config & health checks.")
    ap.add_argument("--profile", default=os.environ.get("LLMC_PROFILE","daily"))
    ap.add_argument("--overlay", action="append", default=[])
    args = ap.parse_args()

    cfg = load_resolved_config(profile=args.profile, mode="yolo", overlays=args.overlay)
    prof = cfg["profiles"][args.profile]
    provider = prof["provider"]
    rag = prof.get("rag", {})
    tools = prof.get("tools", {})

    info(green("== llmc-doctor =="))
    print("Profile:", args.profile)
    print("Provider:", provider)
    print("Model:", prof.get("model"))
    print("RAG enabled:", bool(rag.get("enabled")))
    if rag.get("enabled"):
        print("RAG server:", rag.get("server"), "→", _check_url(rag.get("server")))
    print("Tools enabled:", bool(tools.get("enabled")))

    # Env keys
    env_key = cfg["providers"].get(provider, {}).get("env_key")
    if env_key:
        present = env_key in os.environ
        print("Env key:", env_key, "→", green("OK") if present else red("MISSING"))
