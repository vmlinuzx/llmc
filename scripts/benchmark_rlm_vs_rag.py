#!/usr/bin/env python3
"""
RLM vs Traditional RAG Benchmark Suite

Compares:
1. Context window usage (tokens)
2. Cost per query (USD)
3. Answer quality (correctness, hallucination rate)
4. Latency (time to first token, total time)
5. Multi-hop reasoning capability

Usage:
    python scripts/benchmark_rlm_vs_rag.py --task-set basic
    python scripts/benchmark_rlm_vs_rag.py --task-set advanced --model gpt-4
    python scripts/benchmark_rlm_vs_rag.py --output results.json
"""

import asyncio
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import time
from typing import Literal

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
import typer

# LLMC imports
from llmc.rag.search import search_spans
from llmc.rlm.config import load_rlm_config
from llmc.rlm.session import RLMResult, RLMSession

console = Console()
app = typer.Typer()


@dataclass
class BenchmarkTask:
    """A task to compare RAG vs RLM."""
    
    id: str
    name: str
    question: str
    target_file: str  # File containing the answer
    expected_answer_contains: list[str]  # Strings that should appear in correct answer
    requires_multi_hop: bool  # Does this need to traverse multiple files?
    difficulty: Literal["easy", "medium", "hard"]


@dataclass
class BenchmarkResult:
    """Results for a single task."""
    
    task_id: str
    method: Literal["rag", "rlm"]
    
    # Performance
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_seconds: float
    
    # Quality
    answer: str
    correctness_score: float  # 0.0 - 1.0
    contains_expected: int  # How many expected strings found
    hallucination_detected: bool
    
    # RLM-specific
    subcalls_made: int | None = None
    max_depth: int | None = None
    
    success: bool = True
    error: str | None = None


# ============================================================================
# TASK DEFINITIONS
# ============================================================================

BASIC_TASKS = [
    BenchmarkTask(
        id="basic_001",
        name="Simple function lookup",
        question="What does the RLMSession.load_code_context() method do?",
        target_file="llmc/rlm/session.py",
        expected_answer_contains=["load", "code", "sandbox", "inject"],
        requires_multi_hop=False,
        difficulty="easy"
    ),
    BenchmarkTask(
        id="basic_002",
        name="Configuration value",
        question="What is the default max_session_budget_usd in RLMConfig?",
        target_file="llmc/rlm/config.py",
        expected_answer_contains=["1.00", "dollar"],
        requires_multi_hop=False,
        difficulty="easy"
    ),
    BenchmarkTask(
        id="basic_003",
        name="Security mechanism",
        question="How does the RLM sandbox prevent file writes?",
        target_file="llmc/rlm/sandbox/process.py",
        expected_answer_contains=["blocked", "builtin", "open"],
        requires_multi_hop=False,
        difficulty="medium"
    ),
]

ADVANCED_TASKS = [
    BenchmarkTask(
        id="adv_001",
        name="Multi-file data flow",
        question="Trace how budget enforcement works from RLMSession through TokenBudget to LLM calls",
        target_file="llmc/rlm/session.py",
        expected_answer_contains=["TokenBudget", "check_can_call", "record_call", "governance"],
        requires_multi_hop=True,
        difficulty="hard"
    ),
    BenchmarkTask(
        id="adv_002",
        name="Architecture understanding",
        question="How does the MCP server integrate RLM tool with security policies?",
        target_file="llmc_mcp/server.py",
        expected_answer_contains=["mcp_rlm_query", "McpRlmConfig", "policy", "denylist"],
        requires_multi_hop=True,
        difficulty="hard"
    ),
    BenchmarkTask(
        id="adv_003",
        name="Error handling path",
        question="What happens when RLM exceeds its budget during a recursive call?",
        target_file="llmc/rlm/governance/budget.py",
        expected_answer_contains=["BudgetExceededError", "max_session_budget_usd", "exception"],
        requires_multi_hop=True,
        difficulty="hard"
    ),
]

HALLUCINATION_TASKS = [
    BenchmarkTask(
        id="hall_001",
        name="Non-existent feature",
        question="How does RLM use LangGraph for orchestration?",
        target_file="llmc/rlm/session.py",
        expected_answer_contains=["does not", "not use", "custom"],  # Should say it DOESN'T use LangGraph
        requires_multi_hop=False,
        difficulty="medium"
    ),
    BenchmarkTask(
        id="hall_002",
        name="Incorrect dependency",
        question="Does RLM use Docker containers for sandboxing in Phase 1?",
        target_file="llmc/rlm/sandbox/process.py",
        expected_answer_contains=["process", "not docker", "subprocess"],
        requires_multi_hop=False,
        difficulty="medium"
    ),
]


# ============================================================================
# RAG BASELINE IMPLEMENTATION
# ============================================================================

async def run_traditional_rag(task: BenchmarkTask, model: str = "gpt-4") -> BenchmarkResult:
    """Traditional RAG: retrieve chunks, stuff into context, query LLM."""
    
    start_time = time.time()
    
    try:
        # Step 1: Semantic search to find relevant chunks
        from llmc.rag.service import RAGService
        
        RAGService()
        search_results = await search_spans(
            query=task.question,
            limit=10,  # Retrieve more chunks to ensure coverage
            repo_root=Path("/home/vmlinux/src/llmc")
        )
        
        # Step 2: Extract and concatenate all chunk text
        context_chunks = []
        for result in search_results:
            if hasattr(result, 'text'):
                context_chunks.append(result.text)
            elif hasattr(result, 'snippet'):
                context_chunks.append(result.snippet)
        
        full_context = "\n\n---\n\n".join(context_chunks)
        
        # Step 3: Build massive prompt
        prompt = f"""You are a code analysis assistant. Answer the question using ONLY the provided code context.

CONTEXT:
{full_context}

QUESTION: {task.question}

Answer concisely and accurately based on the code above."""
        
        # Step 4: Call LLM with stuffed context
        from llmc.backends.litellm_core import LiteLLMCore
        
        backend = LiteLLMCore()
        
        response = await backend.complete(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        answer = response.choices[0].message.content
        
        # Calculate metrics
        input_tokens = len(prompt.split()) * 1.3  # Rough estimate
        output_tokens = len(answer.split()) * 1.3
        total_tokens = int(input_tokens + output_tokens)
        
        # Cost estimation (rough)
        cost_per_1k_input = 0.03 if "gpt-4" in model else 0.0015  # GPT-4 vs GPT-3.5
        cost_per_1k_output = 0.06 if "gpt-4" in model else 0.002
        cost_usd = (input_tokens / 1000 * cost_per_1k_input) + (output_tokens / 1000 * cost_per_1k_output)
        
        # Quality check
        correctness = sum(1 for exp in task.expected_answer_contains if exp.lower() in answer.lower())
        correctness_score = correctness / len(task.expected_answer_contains)
        
        # Hallucination detection (basic)
        hallucination = any(phrase in answer.lower() for phrase in [
            "i don't have access",
            "i cannot see",
            "the code doesn't show",
            "not provided in the context"
        ])
        
        latency = time.time() - start_time
        
        return BenchmarkResult(
            task_id=task.id,
            method="rag",
            total_tokens=total_tokens,
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            cost_usd=cost_usd,
            latency_seconds=latency,
            answer=answer,
            correctness_score=correctness_score,
            contains_expected=correctness,
            hallucination_detected=hallucination,
            success=True
        )
        
    except Exception as e:
        return BenchmarkResult(
            task_id=task.id,
            method="rag",
            total_tokens=0,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            latency_seconds=time.time() - start_time,
            answer="",
            correctness_score=0.0,
            contains_expected=0,
            hallucination_detected=False,
            success=False,
            error=str(e)
        )


# ============================================================================
# RLM IMPLEMENTATION
# ============================================================================

async def run_rlm(task: BenchmarkTask, model: str = "gpt-4") -> BenchmarkResult:
    """RLM: Load file into sandbox, let model navigate via tools."""
    
    start_time = time.time()
    
    try:
        # Load RLM config
        config = load_rlm_config()
        config.root_model = model
        config.sub_model = model
        config.max_session_budget_usd = 2.00  # Allow generous budget for benchmark
        config.trace_enabled = True
        
        # Create session
        session = RLMSession(config)
        
        # Load target file into sandbox (NOT context window!)
        target_path = Path("/home/vmlinux/src/llmc") / task.target_file
        session.load_code_context(target_path)
        
        # Run query
        result: RLMResult = await session.run(task=task.question)
        
        # Extract metrics
        budget = result.budget_summary or {}
        total_tokens = budget.get("total_tokens", 0)
        cost_usd = budget.get("total_cost_usd", 0.0)
        
        # Quality check
        answer = result.answer or ""
        correctness = sum(1 for exp in task.expected_answer_contains if exp.lower() in answer.lower())
        correctness_score = correctness / len(task.expected_answer_contains)
        
        hallucination = not result.success or "error" in answer.lower()
        
        latency = time.time() - start_time
        
        return BenchmarkResult(
            task_id=task.id,
            method="rlm",
            total_tokens=total_tokens,
            input_tokens=budget.get("total_tokens", 0) - budget.get("completion_tokens", 0),
            output_tokens=budget.get("completion_tokens", 0),
            cost_usd=cost_usd,
            latency_seconds=latency,
            answer=answer,
            correctness_score=correctness_score,
            contains_expected=correctness,
            hallucination_detected=hallucination,
            subcalls_made=budget.get("sub_calls", 0),
            max_depth=budget.get("max_subcall_depth", 0),
            success=result.success,
            error=result.error
        )
        
    except Exception as e:
        return BenchmarkResult(
            task_id=task.id,
            method="rlm",
            total_tokens=0,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            latency_seconds=time.time() - start_time,
            answer="",
            correctness_score=0.0,
            contains_expected=0,
            hallucination_detected=False,
            success=False,
            error=str(e)
        )


# ============================================================================
# BENCHMARK RUNNER
# ============================================================================

async def run_benchmark(
    tasks: list[BenchmarkTask],
    model: str,
    skip_rag: bool = False,
    skip_rlm: bool = False
) -> list[BenchmarkResult]:
    """Run all tasks for both methods."""
    
    results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        for task in tasks:
            # Run RAG
            if not skip_rag:
                task_progress = progress.add_task(f"[cyan]RAG: {task.name}...", total=None)
                rag_result = await run_traditional_rag(task, model)
                results.append(rag_result)
                progress.remove_task(task_progress)
            
            # Run RLM
            if not skip_rlm:
                task_progress = progress.add_task(f"[green]RLM: {task.name}...", total=None)
                rlm_result = await run_rlm(task, model)
                results.append(rlm_result)
                progress.remove_task(task_progress)
    
    return results


# ============================================================================
# RESULTS ANALYSIS
# ============================================================================

def analyze_results(results: list[BenchmarkResult]):
    """Compare RAG vs RLM performance."""
    
    rag_results = [r for r in results if r.method == "rag"]
    rlm_results = [r for r in results if r.method == "rlm"]
    
    def avg(items, key):
        values = [getattr(r, key) for r in items if r.success]
        return sum(values) / len(values) if values else 0
    
    # Comparison table
    table = Table(title="RAG vs RLM Benchmark Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Traditional RAG", style="yellow")
    table.add_column("RLM", style="green")
    table.add_column("Improvement", style="magenta")
    
    # Token usage
    rag_tokens = avg(rag_results, "total_tokens")
    rlm_tokens = avg(rlm_results, "total_tokens")
    token_reduction = ((rag_tokens - rlm_tokens) / rag_tokens * 100) if rag_tokens > 0 else 0
    table.add_row(
        "Avg Tokens",
        f"{rag_tokens:,.0f}",
        f"{rlm_tokens:,.0f}",
        f"{token_reduction:+.1f}%"
    )
    
    # Cost
    rag_cost = avg(rag_results, "cost_usd")
    rlm_cost = avg(rlm_results, "cost_usd")
    cost_reduction = ((rag_cost - rlm_cost) / rag_cost * 100) if rag_cost > 0 else 0
    table.add_row(
        "Avg Cost (USD)",
        f"${rag_cost:.4f}",
        f"${rlm_cost:.4f}",
        f"{cost_reduction:+.1f}%"
    )
    
    # Latency
    rag_latency = avg(rag_results, "latency_seconds")
    rlm_latency = avg(rlm_results, "latency_seconds")
    latency_change = ((rlm_latency - rag_latency) / rag_latency * 100) if rag_latency > 0 else 0
    table.add_row(
        "Avg Latency (s)",
        f"{rag_latency:.2f}",
        f"{rlm_latency:.2f}",
        f"{latency_change:+.1f}%"
    )
    
    # Correctness
    rag_correctness = avg(rag_results, "correctness_score")
    rlm_correctness = avg(rlm_results, "correctness_score")
    correctness_change = ((rlm_correctness - rag_correctness) / rag_correctness * 100) if rag_correctness > 0 else 0
    table.add_row(
        "Avg Correctness",
        f"{rag_correctness:.2%}",
        f"{rlm_correctness:.2%}",
        f"{correctness_change:+.1f}%"
    )
    
    # Hallucinations
    rag_hallucinations = sum(1 for r in rag_results if r.hallucination_detected)
    rlm_hallucinations = sum(1 for r in rlm_results if r.hallucination_detected)
    table.add_row(
        "Hallucinations",
        str(rag_hallucinations),
        str(rlm_hallucinations),
        f"{rlm_hallucinations - rag_hallucinations:+d}"
    )
    
    # Success rate
    rag_success = sum(1 for r in rag_results if r.success) / len(rag_results) * 100 if rag_results else 0
    rlm_success = sum(1 for r in rlm_results if r.success) / len(rlm_results) * 100 if rlm_results else 0
    table.add_row(
        "Success Rate",
        f"{rag_success:.1f}%",
        f"{rlm_success:.1f}%",
        f"{rlm_success - rag_success:+.1f}%"
    )
    
    console.print(table)
    
    # RLM-specific stats
    if rlm_results:
        console.print("\n[bold]RLM-Specific Metrics:[/bold]")
        avg_subcalls = avg(rlm_results, "subcalls_made")
        avg_depth = avg([r for r in rlm_results if r.max_depth], "max_depth")
        console.print(f"  Average subcalls per query: {avg_subcalls:.1f}")
        console.print(f"  Average recursion depth: {avg_depth:.1f}")


# ============================================================================
# CLI
# ============================================================================

@app.command()
def main(
    task_set: str = typer.Option("basic", help="Task set: basic, advanced, hallucination, all"),
    model: str = typer.Option("gpt-4", help="LLM model to use"),
    output: Path = typer.Option(None, help="Save results to JSON file"),
    skip_rag: bool = typer.Option(False, help="Skip traditional RAG (RLM only)"),
    skip_rlm: bool = typer.Option(False, help="Skip RLM (RAG only)"),
):
    """Run RLM vs RAG benchmark suite."""
    
    # Select tasks
    if task_set == "basic":
        tasks = BASIC_TASKS
    elif task_set == "advanced":
        tasks = ADVANCED_TASKS
    elif task_set == "hallucination":
        tasks = HALLUCINATION_TASKS
    elif task_set == "all":
        tasks = BASIC_TASKS + ADVANCED_TASKS + HALLUCINATION_TASKS
    else:
        console.print(f"[red]Unknown task set: {task_set}[/red]")
        raise typer.Exit(1)
    
    console.print(f"[bold]Running {len(tasks)} tasks with model: {model}[/bold]\n")
    
    # Run benchmark
    results = asyncio.run(run_benchmark(tasks, model, skip_rag, skip_rlm))
    
    # Analyze
    analyze_results(results)
    
    # Save results
    if output:
        output.write_text(json.dumps([asdict(r) for r in results], indent=2))
        console.print(f"\n[green]Results saved to {output}[/green]")
    
    console.print("\n[bold green]✓ Benchmark complete[/bold green]")


if __name__ == "__main__":
    app()
