#!/usr/bin/env python3
"""
mcrun - Run commands with structured output.

Like subprocess.run, but with structured JSON output for tool calling.

Usage:
    mcrun "ls -la"
    mcrun --cwd /tmp "pwd"
    mcrun --json "echo hello"
    mcrun --timeout 30 "long_running_command"

This is a thin UX wrapper for command execution with:
- Structured output (exit code, stdout, stderr)
- Timeout support
- JSON output for programmatic use
- 100% local operation
"""

from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess

from rich.console import Console
import typer

from llmc.core import find_repo_root
from llmc.training_data import ToolCallExample, emit_training_example

console = Console()

app = typer.Typer(
    name="mcrun",
    help="Run commands with structured output.",
    add_completion=False,
)


def _run_command(
    command: str,
    cwd: Path | None = None,
    timeout: int | None = None,
    capture: bool = True,
) -> dict:
    """Execute a command and return structured result."""
    try:
        # Parse command - support both string and list
        if isinstance(command, str):
            args = shlex.split(command)
        else:
            args = command
        
        result = subprocess.run(
            args,
            check=False, cwd=cwd,
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
        
        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout if capture else "",
            "stderr": result.stderr if capture else "",
            "command": command,
            "cwd": str(cwd) if cwd else None,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": e.stdout or "" if hasattr(e, 'stdout') else "",
            "stderr": f"Command timed out after {timeout}s",
            "command": command,
            "cwd": str(cwd) if cwd else None,
            "error": "timeout",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command not found: {shlex.split(command)[0] if command else 'empty'}",
            "command": command,
            "cwd": str(cwd) if cwd else None,
            "error": "not_found",
        }
    except Exception as e:
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "command": command,
            "cwd": str(cwd) if cwd else None,
            "error": "exception",
        }


def _emit_human(result: dict) -> None:
    """Human-readable output."""
    if result["success"]:
        console.print(f"[green]✓[/green] Exit code: {result['exit_code']}")
    else:
        console.print(f"[red]✗[/red] Exit code: {result['exit_code']}")
    
    if result.get("cwd"):
        console.print(f"[dim]CWD: {result['cwd']}[/dim]")
    
    if result["stdout"]:
        console.print("\n[bold]Output:[/bold]")
        # Limit output for readability
        lines = result["stdout"].split("\n")
        if len(lines) > 50:
            console.print("\n".join(lines[:50]))
            console.print(f"\n[dim]... ({len(lines) - 50} more lines)[/dim]")
        else:
            console.print(result["stdout"].rstrip())
    
    if result["stderr"] and not result["success"]:
        console.print("\n[bold red]Stderr:[/bold red]")
        console.print(result["stderr"].rstrip())


def _emit_json(result: dict) -> None:
    """JSON output for programmatic use."""
    print(json.dumps(result, indent=2))


@app.callback(invoke_without_command=True)
def run(
    command: str = typer.Argument(None, help="Command to run"),
    cwd: str = typer.Option(None, "--cwd", "-C", help="Working directory"),
    timeout: int = typer.Option(None, "-t", "--timeout", help="Timeout in seconds"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress output, just return exit code"),
    emit_training: bool = typer.Option(False, "--emit-training", help="Output OpenAI-format training data"),
):
    """
    Run a command and capture output.

    Examples:
        mcrun "ls -la"
        mcrun --cwd /tmp "pwd"
        mcrun --json "echo hello"
        mcrun -t 10 "sleep 5"
    """
    if command is None:
        console.print(
            "[bold]mcrun[/bold] - Run commands with structured output.\n"
        )
        console.print("[dim]Usage:[/dim]")
        console.print(
            '  mcrun [green]"command"[/green]          Run a command'
        )
        console.print(
            "  mcrun [green]--json[/green] \"cmd\"       JSON output"
        )
        console.print(
            "  mcrun [green]--cwd /path[/green] \"cmd\"  Run in directory"
        )
        console.print()
        console.print("[dim]Examples:[/dim]")
        console.print('  mcrun "ls -la"')
        console.print('  mcrun --json "git status"')
        console.print('  mcrun --cwd /tmp "pwd"')
        console.print('  mcrun -t 10 "sleep 5"')
        console.print()
        console.print("[dim]Run 'mcrun --help' for full options.[/dim]")
        return
    
    # Resolve CWD
    work_dir = None
    if cwd:
        work_dir = Path(cwd).resolve()
        if not work_dir.exists():
            console.print(f"[red]Directory not found:[/red] {cwd}")
            raise typer.Exit(1)
    else:
        # Try to use repo root if available
        try:
            work_dir = find_repo_root()
        except Exception:
            work_dir = Path.cwd()
    
    result = _run_command(command, work_dir, timeout)
    
    # Training data mode
    if emit_training:
        _emit_run_training(command, result, cwd)
        return
    
    if quiet:
        raise typer.Exit(0 if result["success"] else result["exit_code"])
    
    if json_output:
        _emit_json(result)
    else:
        _emit_human(result)
    
    # Exit with command's exit code
    if not result["success"]:
        raise typer.Exit(result["exit_code"] if result["exit_code"] > 0 else 1)


def _emit_run_training(command: str, result: dict, cwd: str | None) -> None:
    """Emit OpenAI-format training data for this command run."""
    # Build concise output
    output = result["stdout"]
    if len(output) > 500:
        output = output[:497] + "..."
    
    if result["success"]:
        tool_output = f"Exit code: 0\n{output}"
    else:
        tool_output = f"Exit code: {result['exit_code']}\n{result['stderr']}"
    
    arguments = {"command": command}
    if cwd:
        arguments["cwd"] = cwd
    
    example = ToolCallExample(
        tool_name="run_cmd",
        arguments=arguments,
        user_query=f"Run: {command}",
        tool_output=tool_output,
    )
    
    print(emit_training_example(example, include_schema=True))


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
