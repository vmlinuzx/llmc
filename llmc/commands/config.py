#!/usr/bin/env python3
"""
Config command - Interactive configuration management.

Provides:
- wizard: Interactive setup wizard
- edit: TUI for editing enrichment chains
"""

from pathlib import Path

import typer

from llmc.core import find_repo_root

app = typer.Typer(
    help="Configuration management: wizard, edit, validation.",
    no_args_is_help=True,
)


@app.command("wizard")
def wizard(
    models_only: bool = typer.Option(
        False, "--models-only", help="Only configure models (updates existing config)"
    ),
):
    """
    Run interactive configuration wizard.

    Guides you through:
    1. connecting to Ollama
    2. selecting models
    3. setting up embeddings
    4. generating llmc.toml
    """
    from llmc.commands.wizard import run_wizard

    try:
        repo_root = find_repo_root()
    except Exception:
        # If not in a repo, maybe we are running init?
        # But config wizard usually implies we want to configure the current repo.
        # Fallback to current directory if find_repo_root fails
        repo_root = Path.cwd()

    run_wizard(repo_path=repo_root, models_only=models_only)


@app.command("edit")
def edit(
    config_path: Path = typer.Option(
        None,
        "--config-path",
        "-c",
        help="Path to llmc.toml (default: auto-detect from repo root)",
    )
) -> None:
    """
    Launch the interactive enrichment config TUI.

    Provides a visual editor for managing enrichment chains, routes, and cascades
    in llmc.toml without manual TOML editing.
    """
    # Auto-detect config path if not provided
    if config_path is None:
        try:
            repo_root = find_repo_root()
            config_path = repo_root / "llmc.toml"
        except Exception as e:
            typer.echo(f"Error: Could not find llmc.toml: {e}", err=True)
            typer.echo("Hint: Run from repo root or use --config-path", err=True)
            raise typer.Exit(1)

    if not config_path.exists():
        typer.echo(f"Error: Config file not found: {config_path}", err=True)
        raise typer.Exit(1)

    # Check if textual is installed
    try:
        from llmc.config.tui import run_tui
    except ImportError as e:
        typer.echo("Error: Missing required dependency for TUI", err=True)
        typer.echo(f"  {e}", err=True)
        typer.echo("\nInstall with: pip install textual", err=True)
        raise typer.Exit(1)

    # Launch TUI
    try:
        run_tui(config_path)
    except KeyboardInterrupt:
        typer.echo("\nInterrupted by user", err=True)
        raise typer.Exit(130)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        import traceback

        traceback.print_exc()
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
