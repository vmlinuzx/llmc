from pathlib import Path
import sys

# Add repo root to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

try:
    from llmc.rag_repo.cli_entry import snapshot_workspace_cmd

    print("Successfully imported snapshot_workspace_cmd")

    # create dummy args
    try:
        # This should crash because SafeFS is missing
        snapshot_workspace_cmd(
            repo_root=repo_root,
            workspace=None,
            export=None,
            name="test.tar.gz",
            include_hidden=False,
            force=True,
        )
    except NameError as e:
        print(f"Caught expected error: {e}")
        exit(0)  # Success - we found the bug
    except Exception as e:
        print(f"Caught unexpected error: {e}")
        exit(1)

except ImportError as e:
    print(f"Import failed: {e}")
    exit(1)
