#!/usr/bin/env python3
import os, subprocess, sys, shutil, json, textwrap

def run(cmd):
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)

def main():
    venv = ".venv"
    if not os.path.exists(venv):
        run([sys.executable, "-m", "venv", venv])
    pip = os.path.join(venv, "bin", "pip")
    py = os.path.join(venv, "bin", "python")
    rag = os.path.join(venv, "bin", "rag")
    run([pip, "install", "-U", "pip", "wheel"])
    run([pip, "install", "-e", "."])
    print("\nBootstrapped. Try:")
    print(f"  {rag} index")
    print(f"  {rag} search 'entrypoint for RAG'")
    print("\nOptional API:")
    print(f"  {pip} install fastapi uvicorn")
    print(f"  {py} api/server.py")

if __name__ == "__main__":
    main()
