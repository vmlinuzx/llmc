"""RLM CLI commands - agentic code analysis."""

import asyncio
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
import json

from llmc.rlm.config import RLMConfig
from llmc.rlm.session import RLMSession, RLMResult

app = typer.Typer(help="RLM - Recursive Language Model for code analysis")
console = Console()


@app.command()
def query(
    task: str = typer.Argument(..., help="Analysis task/question"),
    file: Path = typer.Option(None, "--file", "-f", help="Source file to analyze"),
    context: Path = typer.Option(None, "--context", "-c", help="Raw context file"),
    model: str = typer.Option(None, "--model", help="Override root model (e.g., deepseek/deepseek-reasoner)"),
    budget: float = typer.Option(None, "--budget", help="Override budget limit (USD)"),
    trace: bool = typer.Option(False, "--trace", help="Show execution trace"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON instead of formatted"),
):
    """Run RLM analysis on code or context.
    
    Examples:
        llmc rlm query "What does this file do?" --file mycode.py
        llmc rlm query "Find the bug" --file buggy.py --model deepseek/deepseek-reasoner
        llmc rlm query "Summarize this" --context data.txt --budget 0.50
    """
    asyncio.run(_run_query(task, file, context, model, budget, trace, json_output))


async def _run_query(
    task: str,
    file: Path | None,
    context: Path | None,
    model: str | None,
    budget: float | None,
    trace: bool,
    json_output: bool,
):
    # Validate inputs
    if not file and not context:
        console.print("[red]Error: Must provide --file or --context[/red]")
        raise typer.Exit(1)
    
    if file and context:
        console.print("[red]Error: Cannot use both --file and --context[/red]")
        raise typer.Exit(1)
    
    # Load config
    config = RLMConfig()
    if model:
        config.root_model = model
        config.sub_model = model
    if budget:
        config.max_session_budget_usd = budget
    config.trace_enabled = trace
    
    # Create session
    session = RLMSession(config)
    
    # Load context
    if not json_output:
        console.print(f"[cyan]Loading context...[/cyan]")
    
    if file:
        if not file.exists():
            console.print(f"[red]Error: File not found: {file}[/red]")
            raise typer.Exit(1)
        meta = session.load_code_context(file)
    else:
        meta = session.load_context(context)
    
    if not json_output:
        console.print(f"[green]Context loaded:[/green] {meta['total_chars']:,} chars, ~{meta['estimated_tokens']:,} tokens")
        console.print(f"[cyan]Model:[/cyan] {config.root_model}")
        console.print(f"[cyan]Budget:[/cyan] ${config.max_session_budget_usd:.2f}")
        console.print()
        console.print(Panel(f"[bold]{task}[/bold]", title="Task", border_style="blue"))
        console.print()
        console.print("[yellow]Running RLM session...[/yellow]")
    
    # Run session
    try:
        result: RLMResult = await session.run(task)
        
        if json_output:
            output = {
                "success": result.success,
                "answer": result.answer,
                "error": result.error,
                "budget": result.budget_summary,
                "session_id": result.session_id,
            }
            if trace and result.trace:
                output["trace"] = result.trace
            console.print(json.dumps(output, indent=2))
        else:
            _display_result(result, trace)
            
    except Exception as e:
        if json_output:
            console.print(json.dumps({"success": False, "error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _display_result(result: RLMResult, show_trace: bool):
    """Display formatted result."""
    console.print()
    console.print("=" * 80)
    
    if result.success and result.answer:
        console.print(Panel(
            result.answer,
            title="[bold green]✓ Answer[/bold green]",
            border_style="green",
        ))
    elif result.error:
        console.print(Panel(
            result.error,
            title="[bold red]✗ Error[/bold red]",
            border_style="red",
        ))
    else:
        console.print(Panel(
            "No answer received (max turns reached or budget exceeded)",
            title="[bold yellow]⚠ Incomplete[/bold yellow]",
            border_style="yellow",
        ))
    
    # Budget summary
    if result.budget_summary:
        console.print()
        console.print("[bold]Budget Summary:[/bold]")
        b = result.budget_summary
        console.print(f"  Cost: ${b['total_cost_usd']:.4f} / ${b['budget_usd']:.2f} ({b['budget_used_pct']:.1f}%)")
        console.print(f"  Root: {b['root_calls']} calls, ${b['root_cost_usd']:.4f}")
        console.print(f"  Sub: {b['sub_calls']} calls, ${b['sub_cost_usd']:.4f}, max depth {b['max_subcall_depth']}")
        console.print(f"  Tokens: {b['total_tokens']:,}")
        console.print(f"  Time: {b['elapsed_seconds']:.1f}s")
    
    # Trace
    if show_trace and result.trace:
        console.print()
        console.print("[bold]Execution Trace:[/bold]")
        for i, event in enumerate(result.trace):
            console.print(f"  {i+1}. [{event['event']}] {json.dumps({k: v for k, v in event.items() if k not in ['event', 'timestamp', 'session_id']})}")


if __name__ == "__main__":
    app()
