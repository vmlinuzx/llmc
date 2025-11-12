#!/usr/bin/env python3
import os, subprocess, sys


def run(*args):
    print("+", " ".join(args))
    subprocess.check_call(args)


def main():
    venv = ".venv"
    if not os.path.exists(venv):
        run(sys.executable, "-m", "venv", venv)
    pip = os.path.join(venv, "bin", "pip")
    uvicorn = os.path.join(venv, "bin", "uvicorn")
    rag = os.path.join(venv, "bin", "rag")
    run(pip, "install", "-U", "pip", "wheel")
    run(pip, "install", "-e", ".[api,embed]")
    print("\nBootstrapped. Try:")
    print(f"  {rag} index && {rag} embed --execute")
    print(f"  {rag} search 'entrypoint for RAG' --json")
    print("\nOptional API:")
    print(f"  {uvicorn} api.server:app --reload")


if __name__ == "__main__":
    main()

