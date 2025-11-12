#!/usr/bin/env python3
"""Create (or update) the LLMC production kit files in the current directory,
then package them into llmc_production_kit.zip.

Usage:
  python scripts/build_kit.py
"""
import os, zipfile, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "llmc_production_kit.zip"

INCLUDE = [
    "README_SHIP.md",
    "SDD.md",
    "pyproject.toml",
    "llmc.toml",
    "Dockerfile",
    "compose.yaml",
    "Makefile",
    ".github/workflows/index.yml",
    "api/server.py",
    "scripts/bootstrap.py",
    "scripts/build_kit.py",
    "prompts/porting_agent.md",
]

def main():
    # ensure paths exist
    (ROOT / "api").mkdir(parents=True, exist_ok=True)
    (ROOT / "scripts").mkdir(parents=True, exist_ok=True)
    (ROOT / ".github/workflows").mkdir(parents=True, exist_ok=True)
    (ROOT / "prompts").mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in INCLUDE:
            path = ROOT / rel
            if path.exists():
                zf.write(path, arcname=rel)
            else:
                print(f"warn: missing {rel}")
    print(f"wrote {OUT}")

if __name__ == "__main__":
    main()
