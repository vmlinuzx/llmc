"""CLI for managing LLMC MCP daemon."""

from __future__ import annotations

from pathlib import Path
import subprocess

from rich.console import Console
from rich.table import Table
import typer

app = typer.Typer(
    name="llmc-mcp",
    help="LLMC MCP Server management CLI",
    add_completion=False,
)
console = Console()


@app.command()
def start(
    foreground: bool = typer.Option(
        False, "--foreground", "-f", help="Run in foreground (don't daemonize)"
    ),
    port: int = typer.Option(8765, "--port", "-p", help="HTTP port"),
    host: str = typer.Option("127.0.0.1", "--host", "-H", help="Bind address"),
) -> None:
    """Start the MCP daemon."""
    from llmc_mcp.config import load_config
    from llmc_mcp.daemon import MCPDaemon
    from llmc_mcp.server import LlmcMcpServer
    from llmc_mcp.transport import MCPHttpServer

    # Load config
    config = load_config()

    # Override port/host if specified
    config.server.port = port
    config.server.host = host

    # Create server factory
    def server_factory():
        mcp_server = LlmcMcpServer(config)
        return MCPHttpServer(mcp_server, config, host=host, port=port)

    daemon = MCPDaemon(server_factory)

    if daemon.start(foreground=foreground):
        if foreground:
            console.print(f"[green]✓[/] MCP server running on http://{host}:{port}")
            console.print("  Press Ctrl+C to stop")
        else:
            status = daemon.status()
            console.print(f"[green]✓[/] MCP daemon started (PID {status['pid']})")
            console.print(f"  Listening: http://{host}:{port}")
            console.print(f"  Logs: {status['logfile']}")
            console.print("\nGet your API key with: [bold]llmc-mcp show-key[/]")
    else:
        console.print("[yellow]![/] Daemon already running")
        raise typer.Exit(1)


@app.command()
def stop() -> None:
    """Stop the MCP daemon."""
    from llmc_mcp.daemon import MCPDaemon

    daemon = MCPDaemon(lambda: None)

    if daemon.stop():
        console.print("[green]✓[/] MCP daemon stopped")
    else:
        console.print("[yellow]![/] Daemon was not running")
        raise typer.Exit(1)


@app.command()
def restart(
    foreground: bool = typer.Option(
        False, "--foreground", "-f", help="Run in foreground after restart"
    ),
) -> None:
    """Restart the MCP daemon."""
    from llmc_mcp.daemon import MCPDaemon

    daemon = MCPDaemon(lambda: None)

    if daemon.restart(foreground=foreground):
        console.print("[green]✓[/] MCP daemon restarted")
    else:
        console.print("[red]✗[/] Failed to restart daemon")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Show daemon status."""
    from llmc_mcp.daemon import MCPDaemon

    daemon = MCPDaemon(lambda: None)
    info = daemon.status()

    if info["running"]:
        console.print(f"[green]●[/] MCP daemon is [bold]running[/] (PID {info['pid']})")
    else:
        console.print("[red]●[/] MCP daemon is [bold]stopped[/]")

    # Show paths
    table = Table(show_header=False)
    table.add_row("Pidfile:", info["pidfile"])
    table.add_row("Logfile:", info["logfile"])
    console.print(table)


@app.command()
def logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
) -> None:
    """Show daemon logs."""
    from llmc_mcp.daemon import MCPDaemon

    daemon = MCPDaemon(lambda: None)
    logfile = daemon.LOGFILE

    if not logfile.exists():
        console.print("[yellow]No logs found yet[/]")
        raise typer.Exit(1)

    if follow:
        subprocess.run(["tail", "-f", str(logfile)], check=False)
    else:
        subprocess.run(["tail", "-n", str(lines), str(logfile)], check=False)


@app.command(name="show-key")
def show_key() -> None:
    """Display the API key for connecting to the daemon."""
    key_path = Path.home() / ".llmc" / "mcp-api-key"

    if key_path.exists():
        key = key_path.read_text().strip()
        console.print("\n[bold]API Key:[/]", key)
        console.print("\n[dim]Use in client with:[/dim]")
        console.print(f"  [cyan]X-API-Key: {key}[/cyan]")
        console.print(f"  [cyan]curl http://localhost:8765/sse?api_key={key}[/cyan]")
    else:
        console.print(
            "[yellow]No API key generated yet. Start the daemon first:[/] [bold]llmc-mcp start[/]"
        )
        raise typer.Exit(1)


@app.command()
def health() -> None:
    """Quick health check (for scripts, exit code 0 = healthy)."""
    import httpx

    from llmc_mcp.config import load_config
    from llmc_mcp.daemon import MCPDaemon

    daemon = MCPDaemon(lambda: None)

    # Check if daemon is running
    if not daemon._is_running():
        console.print("[red]✗[/] Daemon not running")
        raise typer.Exit(1)

    # Check HTTP endpoint
    config = load_config()
    url = f"http://{config.server.host}:{config.server.port}/health"

    try:
        r = httpx.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            console.print(f"[green]✓[/] Daemon healthy ({data.get('tools', 0)} tools)")
            raise typer.Exit(0)
        else:
            console.print(f"[red]✗[/] Health check failed (HTTP {r.status_code})")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/] Health check failed: {e}")
        raise typer.Exit(1) from None


def main() -> None:
    """Entry point for llmc-mcp CLI."""
    app()


if __name__ == "__main__":
    main()
