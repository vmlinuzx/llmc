#!/usr/bin/env python3
"""
Quick RLM Benchmark - Uses DeepSeek & MiniMax from .env

Tests RLM's core thesis with cheap, fast models:
1. Context window reduction
2. Multi-hop reasoning
3. Cost savings

Usage:
    python scripts/benchmark_rlm_quick.py                    # Run all tests
    python scripts/benchmark_rlm_quick.py --model deepseek    # DeepSeek only
    python scripts/benchmark_rlm_quick.py --model minimax     # MiniMax only
    python scripts/benchmark_rlm_quick.py --verbose           # Show full answers
"""

import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import typer

from llmc.rlm.config import load_rlm_config

# LLMC imports
from llmc.rlm.session import RLMResult, RLMSession

console = Console()
app = typer.Typer()


@dataclass
class QuickTest:
    """A quick validation test."""
    
    name: str
    file: str
    question: str
    expected_keywords: list[str]  # Answer should contain these
    requires_navigation: bool  # Does this need AST tools?


# Define quick tests
TESTS = [
    QuickTest(
        name="Simple lookup",
        file="llmc/rlm/config.py",
        question="What is the default max_session_budget_usd value?",
        expected_keywords=["1.00", "1.0", "one dollar"],
        requires_navigation=False
    ),
    QuickTest(
        name="Code understanding",
        file="llmc/rlm/session.py",
        question="What does the load_code_context method do?",
        expected_keywords=["load", "sandbox", "inject", "context"],
        requires_navigation=True
    ),
    QuickTest(
        name="Multi-hop trace",
        file="llmc/rlm/session.py",
        question="How does budget enforcement work? Trace from check to exception.",
        expected_keywords=["TokenBudget", "check_can_call", "BudgetExceededError", "governance"],
        requires_navigation=True
    ),
    QuickTest(
        name="Security check",
        file="llmc/rlm/sandbox/process.py",
        question="List the blocked builtins that prevent file writes.",
        expected_keywords=["open", "exec", "eval", "blocked"],
        requires_navigation=True
    ),
]


async def run_rlm_test(test: QuickTest, model: str) -> dict:
    """Run single RLM test."""
    
    start_time = time.time()
    
    try:
        # Load config
        config = load_rlm_config()
        
        # Set model based on choice
        if model == "deepseek":
            config.root_model = "deepseek/deepseek-chat"
            config.sub_model = "deepseek/deepseek-chat"
        elif model == "minimax":
            config.root_model = "minimax/abab6.5s-chat"
            config.sub_model = "minimax/abab6.5s-chat"
        else:
            # Use whatever is in config
            pass
        
        config.max_session_budget_usd = 0.50  # Cheap tests
        config.trace_enabled = True
        
        # Create session
        session = RLMSession(config)
        
        # Load file
        target_path = Path("/home/vmlinux/src/llmc") / test.file
        if not target_path.exists():
            return {
                "success": False,
                "error": f"File not found: {target_path}",
                "model": config.root_model
            }
        
        session.load_code_context(target_path)
        
        # Run query
        result: RLMResult = await session.run(task=test.question, max_turns=10)
        
        # Check answer quality
        answer = result.answer or ""
        keywords_found = [kw for kw in test.expected_keywords if kw.lower() in answer.lower()]
        correctness = len(keywords_found) / len(test.expected_keywords)
        
        # Extract metrics
        budget = result.budget_summary or {}
        
        elapsed = time.time() - start_time
        
        return {
            "success": result.success,
            "answer": answer,
            "correctness": correctness,
            "keywords_found": keywords_found,
            "keywords_missing": [kw for kw in test.expected_keywords if kw not in keywords_found],
            "total_tokens": budget.get("total_tokens", 0),
            "cost_usd": budget.get("total_cost_usd", 0.0),
            "subcalls": budget.get("sub_calls", 0),
            "max_depth": budget.get("max_subcall_depth", 0),
            "latency_seconds": elapsed,
            "model": config.root_model,
            "error": result.error
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latency_seconds": time.time() - start_time
        }


async def run_all_tests(model_choice: str, verbose: bool):
    """Run all tests and display results."""
    
    console.print("\n[bold]Running RLM Quick Benchmark[/bold]")
    console.print(f"Model: {model_choice}\n")
    
    results = []
    
    for i, test in enumerate(TESTS, 1):
        console.print(f"[cyan]Test {i}/{len(TESTS)}: {test.name}[/cyan]")
        
        result = await run_rlm_test(test, model_choice)
        results.append((test, result))
        
        # Show result
        if result["success"]:
            correctness = result["correctness"] * 100
            color = "green" if correctness >= 75 else "yellow" if correctness >= 50 else "red"
            console.print(f"  [{color}]✓ {correctness:.0f}% correct[/{color}] "
                         f"({result['total_tokens']} tokens, ${result['cost_usd']:.4f}, "
                         f"{result['subcalls']} subcalls, {result['latency_seconds']:.1f}s)")
            
            if verbose:
                console.print(Panel(result["answer"][:500], title="Answer Preview", border_style="dim"))
        else:
            console.print(f"  [red]✗ Failed: {result.get('error', 'Unknown error')}[/red]")
        
        console.print()
    
    # Summary table
    console.print("\n[bold]═══ Summary ═══[/bold]\n")
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Test")
    table.add_column("Result", justify="center")
    table.add_column("Correctness", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Subcalls", justify="right")
    table.add_column("Time", justify="right")
    
    for test, result in results:
        if result["success"]:
            correctness = f"{result['correctness']*100:.0f}%"
            color = "green" if result['correctness'] >= 0.75 else "yellow"
            status = f"[{color}]✓[/{color}]"
            table.add_row(
                test.name,
                status,
                correctness,
                f"{result['total_tokens']:,}",
                f"${result['cost_usd']:.4f}",
                str(result['subcalls']),
                f"{result['latency_seconds']:.1f}s"
            )
        else:
            table.add_row(test.name, "[red]✗[/red]", "-", "-", "-", "-", "-")
    
    console.print(table)
    
    # Calculate aggregates
    successful = [r for _, r in results if r["success"]]
    if successful:
        console.print("\n[bold]Aggregate Stats:[/bold]")
        console.print(f"  Success rate: {len(successful)}/{len(results)} ({len(successful)/len(results)*100:.0f}%)")
        console.print(f"  Avg correctness: {sum(r['correctness'] for r in successful)/len(successful)*100:.0f}%")
        console.print(f"  Total tokens: {sum(r['total_tokens'] for r in successful):,}")
        console.print(f"  Total cost: ${sum(r['cost_usd'] for r in successful):.4f}")
        console.print(f"  Avg subcalls: {sum(r['subcalls'] for r in successful)/len(successful):.1f}")
        console.print(f"  Total time: {sum(r['latency_seconds'] for r in successful):.1f}s")
        
        # Context window comparison
        avg_tokens = sum(r['total_tokens'] for r in successful) / len(successful)
        
        # Estimate traditional RAG token usage
        # (would paste entire file into context)
        avg_file_size = 15000  # Rough estimate for Python files
        traditional_tokens = avg_file_size * len(successful)
        savings = (traditional_tokens - sum(r['total_tokens'] for r in successful)) / traditional_tokens * 100
        
        console.print("\n[bold green]Context Window Savings:[/bold green]")
        console.print(f"  Traditional RAG estimate: {traditional_tokens:,} tokens")
        console.print(f"  RLM actual: {sum(r['total_tokens'] for r in successful):,} tokens")
        console.print(f"  Reduction: [bold]{savings:.1f}%[/bold]")
    
    # Save results
    output_file = Path("/tmp/rlm_benchmark_results.json")
    output_file.write_text(json.dumps(
        [{"test": t.name, "result": r} for t, r in results],
        indent=2
    ))
    console.print(f"\n[dim]Results saved to {output_file}[/dim]")


@app.command()
def main(
    model: str = typer.Option("deepseek", help="Model: deepseek, minimax, or config"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full answers"),
):
    """Run quick RLM benchmark with DeepSeek or MiniMax."""
    
    # Verify API keys
    if model == "deepseek" and not os.getenv("DEEPSEEK_API_KEY"):
        console.print("[red]Error: DEEPSEEK_API_KEY not set in .env[/red]")
        raise typer.Exit(1)
    
    if model == "minimax" and not os.getenv("MINIMAX_API_KEY"):
        console.print("[red]Error: MINIMAX_API_KEY not set in .env[/red]")
        raise typer.Exit(1)
    
    asyncio.run(run_all_tests(model, verbose))


if __name__ == "__main__":
    app()
