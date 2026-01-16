"""llmc-cli run - Unified entry point for mc* developer tools.

Usage:
    llmc-cli run mcschema --help          # Show mcschema help
    llmc-cli run mcschema schema --json   # Run with options  
    llmc-cli run mcgrep search "auth"     # Search
    llmc-cli run skeleton --limit 100     # Generate repo skeleton
    llmc-cli run mcread llmc/main.py      # Read a file
    llmc-cli run mcinspect Router         # Inspect a symbol
"""

from __future__ import annotations

from pathlib import Path

import typer

# Import tool apps for multi-command tools
from llmc.mchot import app as mchot_app
from llmc.mcgrep import app as mcgrep_app
from llmc.mcrun import app as mcrun_app
from llmc.mcschema import app as mcschema_app
from llmc.mcwho import app as mcwho_app

app = typer.Typer(
    name="run",
    help="Run mc* developer tools (mcschema, mcgrep, mcwho, etc.)",
    no_args_is_help=True,
)

# Mount multi-command tools as sub-typers (preserves full --help and options)
app.add_typer(mcschema_app, name="mcschema")
app.add_typer(mcgrep_app, name="mcgrep")
app.add_typer(mcwho_app, name="mcwho")
app.add_typer(mchot_app, name="mchot")
app.add_typer(mcrun_app, name="mcrun")


# =============================================================================
# Single-command tools - wrapped as direct commands
# =============================================================================

@app.command("mcread")
def mcread_cmd(
    file_path: str = typer.Argument(..., help="File to read"),
    raw: bool = typer.Option(False, "--raw", help="Skip graph enrichment"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
    start_line: int | None = typer.Option(
        None, "-s", "--start", help="Start line (1-indexed)"
    ),
    end_line: int | None = typer.Option(
        None, "-e", "--end", help="End line (1-indexed)"
    ),
    emit_training: bool = typer.Option(
        False, "--emit-training", help="Output OpenAI-format training data"
    ),
) -> None:
    """Read a file with graph context.
    
    For binary documents (PDF, DOCX, etc.), automatically reads from the
    markdown sidecar if available.
    """
    from llmc.mcread import read_file_command
    read_file_command(
        file_path=file_path,
        raw=raw,
        json_output=json_output,
        start_line=start_line,
        end_line=end_line,
        emit_training=emit_training,
    )


@app.command("mcinspect")
def mcinspect_cmd(
    symbol: str = typer.Argument(
        ..., help="Symbol to inspect (e.g., Router, llmc.router.Router)"
    ),
    full: bool = typer.Option(False, "--full", help="Show full definition"),
    capsule: bool = typer.Option(False, "--capsule", help="Show compact summary"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
    emit_training: bool = typer.Option(
        False, "--emit-training", help="Output OpenAI-format training data"
    ),
) -> None:
    """Inspect a symbol with graph context."""
    from llmc.mcinspect import inspect_symbol_command
    inspect_symbol_command(
        symbol=symbol,
        full=full,
        capsule=capsule,
        json_output=json_output,
        emit_training=emit_training,
    )


# =============================================================================
# Skeleton - Native Typer command (original is Click-based in rag/cli.py)
# =============================================================================

@app.command("skeleton")
def skeleton_cmd(
    output: Path | None = typer.Option(
        None, "-o", "--output", help="Output file path (default: stdout)."
    ),
    limit: int = typer.Option(
        500, "-n", "--limit", show_default=True, help="Maximum files to include."
    ),
) -> None:
    """Generate a minimalist repository skeleton for LLM context."""
    from llmc.core import find_repo_root
    from llmc.rag.skeleton import generate_repo_skeleton
    
    repo_root = find_repo_root()
    skeleton_text = generate_repo_skeleton(repo_root, max_files=limit)
    
    if output:
        output.write_text(skeleton_text, encoding="utf-8")
        typer.echo(f"Wrote skeleton to {output}")
    else:
        typer.echo(skeleton_text)
