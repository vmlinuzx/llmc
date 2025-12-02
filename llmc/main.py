import typer
from typing import Optional
from llmc.core import LLMC_VERSION, find_repo_root, load_config
from llmc.commands.init import init as init_command
from llmc.commands.rag import index, search, inspect, plan, stats, doctor
from llmc.commands.tui import tui, monitor

app = typer.Typer(
    name="llmc",
    help="LLMC: LLM Cost Compression & RAG Tooling",
    add_completion=True,
    no_args_is_help=True
)

app.command(name="init")(init_command)
app.command()(index)
app.command()(search)
app.command()(inspect)
app.command()(plan)
app.command()(stats)
app.command()(doctor)
app.command()(tui)
app.command()(monitor)

def version_callback(value: bool):
    if value:
        root = find_repo_root()
        config = load_config(root)
        typer.echo(f"LLMC v{LLMC_VERSION}")
        typer.echo(f"Root: {root}")
        typer.echo(f"Config: {'Found' if config else 'Missing'}")
        raise typer.Exit()

@app.callback()
def common(
    ctx: typer.Context,
    version: bool = typer.Option(
        None, 
        "--version", 
        "-v", 
        callback=version_callback, 
        help="Show version and exit."
    ),
):
    """
    LLMC Unified CLI
    """
    pass

if __name__ == "__main__":
    app()
