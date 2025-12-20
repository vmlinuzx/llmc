
import typer
from pathlib import Path
from llmc.rmta.runner import RMTARunner
from typing import List

app = typer.Typer(no_args_is_help=True)

@app.command()
def test_mcp(
    mode: str = typer.Option("quick", help="Test mode: quick, standard, ruthless"),
    tools: List[str] = typer.Option(None, "--tools", "-t", help="Specific tools to test"),
    output: Path = typer.Option(None, "--output", "-o", help="Output report path"),
    fail_fast: bool = typer.Option(False, "--fail-fast", "-x", help="Stop on first failure"),
):
    """Run MCP tool tests.

    Modes:
        quick    - Smoke tests only (~30s)
        standard - Core functionality (~2min)
        ruthless - Edge cases, security, performance (~10min)
    """
    if mode not in ["quick", "standard", "ruthless"]:
        print(f"Error: Invalid mode '{mode}'. Please choose from 'quick', 'standard', or 'ruthless'.")
        raise typer.Exit(1)

    runner = RMTARunner(mode=mode, tools=tools, fail_fast=fail_fast)
    report = runner.run()

    if output:
        report.save(output)

    report.print_summary()

    if not all(result.passed for result in report.results):
        raise typer.Exit(1)
