#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def port_to_repo():
    template_dir = Path(__file__).parent
    target_repo = sys.argv[1] if len(sys.argv) > 1 else "."
    
    target_path = Path(target_repo)
    llmc_path = target_path / "llmc"
    
    if llmc_path.exists():
        print(f"llmc/ already exists in {target_repo}")
        return
    
    # Copy template
    import shutil
    shutil.copytree(template_dir, llmc_path)
    print(f"LLMC template deployed to {target_repo}/llmc/")
    
    # Update .gitignore
    gitignore = target_path / ".gitignore"
    if gitignore.exists():
        with open(gitignore, 'a') as f:
            f.write("\n# LLMC Runtime Data\n.llmc/\nlogs/\n.llmc/.rag/\n")
    
    print("Deployment complete!")

if __name__ == "__main__":
    port_to_repo()
