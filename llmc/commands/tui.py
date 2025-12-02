from llmc.core import find_repo_root
from llmc.tui.app import LLMC_TUI


def tui():
    """Launch the interactive TUI."""
    repo_root = find_repo_root()
    # TUI app expects repo_root to be passed or defaults to cwd
    # We pass it explicitly to be safe
    app = LLMC_TUI(repo_root=repo_root)
    app.run()

def monitor():
    """Alias for 'tui' command."""
    tui()
