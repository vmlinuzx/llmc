#!/usr/bin/env python3
"""
Analyze enrichment performance metrics.

This script queries the metrics stored in the enrichments table to help:
1. Compare model performance (T/s between Qwen 3B vs 7B)
2. Identify slow backends
3. Track GPU vs CPU inference speeds
4. Diagnose ROCm vs Vulkan driver performance

Usage:
    python scripts/analyze_enrichment_metrics.py /path/to/repo
    python scripts/analyze_enrichment_metrics.py  # using cwd
"""

import sqlite3
import sys
from pathlib import Path
from dataclasses import dataclass
import statistics


@dataclass  
class ModelMetrics:
    model: str
    count: int
    avg_tps: float
    min_tps: float
    max_tps: float
    p25_tps: float
    p50_tps: float
    p75_tps: float
    avg_eval_count: float
    total_tokens: int
    avg_prompt_tokens: float


def analyze_database(db_path: Path) -> None:
    """Analyze performance metrics from enrichments table."""
    print(f"Analyzing: {db_path}")
    print("=" * 80)
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Check if metrics columns exist
    cur.execute("PRAGMA table_info(enrichments)")
    cols = {row[1] for row in cur.fetchall()}
    
    if "tokens_per_second" not in cols:
        print("Error: No performance metrics found in database.")
        print("Run migrate_add_enrichment_metrics.py first, then enrich some spans.")
        return
    
    # Get enrichments with metrics
    cur.execute("""
        SELECT 
            model,
            tokens_per_second,
            eval_count,
            eval_duration_ns,
            prompt_eval_count,
            total_duration_ns,
            backend_host
        FROM enrichments
        WHERE tokens_per_second IS NOT NULL
        ORDER BY model
    """)
    
    rows = cur.fetchall()
    
    if not rows:
        print("No enrichments with performance metrics found yet.")
        print("New enrichments will include metrics after the code change.")
        return
    
    # Group by model
    model_data: dict[str, list[dict]] = {}
    for model, tps, eval_count, eval_duration, prompt_eval, total_dur, host in rows:
        if model not in model_data:
            model_data[model] = []
        model_data[model].append({
            "tps": tps,
            "eval_count": eval_count or 0,
            "eval_duration": eval_duration or 0,
            "prompt_eval": prompt_eval or 0,
            "total_duration": total_dur or 0,
            "host": host,
        })
    
    print(f"\nFound {len(rows)} enrichments with metrics across {len(model_data)} models\n")
    
    # Calculate stats per model
    print("=" * 80)
    print("MODEL PERFORMANCE COMPARISON")
    print("=" * 80)
    
    print(f"\n{'Model':<40} {'Count':>8} {'Avg T/s':>10} {'P50 T/s':>10} {'P75 T/s':>10}")
    print("-" * 80)
    
    for model, data in sorted(model_data.items(), key=lambda x: -len(x[1])):
        tps_values = [d["tps"] for d in data if d["tps"] and d["tps"] > 0]
        
        if not tps_values:
            continue
            
        avg_tps = statistics.mean(tps_values)
        p50_tps = statistics.median(tps_values)
        p75_tps = statistics.quantiles(tps_values, n=4)[2] if len(tps_values) >= 4 else max(tps_values)
        
        model_short = model[:38] + ".." if len(model) > 40 else model
        print(f"{model_short:<40} {len(data):>8} {avg_tps:>10.1f} {p50_tps:>10.1f} {p75_tps:>10.1f}")
    
    # Detailed stats per model
    print("\n" + "=" * 80)
    print("DETAILED STATISTICS PER MODEL")
    print("=" * 80)
    
    for model, data in sorted(model_data.items(), key=lambda x: -len(x[1])):
        tps_values = [d["tps"] for d in data if d["tps"] and d["tps"] > 0]
        eval_counts = [d["eval_count"] for d in data if d["eval_count"]]
        prompt_counts = [d["prompt_eval"] for d in data if d["prompt_eval"]]
        
        if not tps_values:
            continue
        
        print(f"\n{model}")
        print("-" * 40)
        print(f"  Enrichments:      {len(data):>10,}")
        print(f"  Tokens/sec (avg): {statistics.mean(tps_values):>10.1f}")
        print(f"  Tokens/sec (min): {min(tps_values):>10.1f}")
        print(f"  Tokens/sec (max): {max(tps_values):>10.1f}")
        
        if len(tps_values) >= 4:
            q = statistics.quantiles(tps_values, n=4)
            print(f"  Tokens/sec (P25): {q[0]:>10.1f}")
            print(f"  Tokens/sec (P50): {q[1]:>10.1f}")
            print(f"  Tokens/sec (P75): {q[2]:>10.1f}")
        
        if eval_counts:
            print(f"  Avg output tokens:{statistics.mean(eval_counts):>10.1f}")
            print(f"  Total tokens:     {sum(eval_counts):>10,}")
        
        if prompt_counts:
            print(f"  Avg input tokens: {statistics.mean(prompt_counts):>10.1f}")
        
        # Host distribution
        hosts = {}
        for d in data:
            host = d.get("host") or "unknown"
            hosts[host] = hosts.get(host, 0) + 1
        
        if len(hosts) > 1 or list(hosts.keys())[0] != "unknown":
            print(f"  Hosts:")
            for host, count in sorted(hosts.items(), key=lambda x: -x[1]):
                pct = count / len(data) * 100
                print(f"    {host}: {count} ({pct:.1f}%)")
    
    # Performance classification
    print("\n" + "=" * 80)
    print("PERFORMANCE CLASSIFICATION")
    print("=" * 80)
    
    for model, data in sorted(model_data.items(), key=lambda x: -len(x[1])):
        tps_values = [d["tps"] for d in data if d["tps"] and d["tps"] > 0]
        if not tps_values:
            continue
            
        avg_tps = statistics.mean(tps_values)
        
        if avg_tps < 5:
            tier = "🐢 Very Slow (likely CPU)"
        elif avg_tps < 15:
            tier = "🐇 Slow (entry GPU or CPU)"
        elif avg_tps < 30:
            tier = "⚡ Moderate (typical GPU)"
        elif avg_tps < 60:
            tier = "🚀 Fast (good GPU)"
        else:
            tier = "🔥 Very Fast (high-end GPU)"
        
        model_short = model[:40] if len(model) <= 40 else model[:38] + ".."
        print(f"  {model_short}: {avg_tps:.1f} T/s → {tier}")
    
    conn.close()


def find_rag_database(repo_path: Path) -> Path | None:
    """Find the RAG database in a repo."""
    candidates = [
        repo_path / ".rag" / "index_v2.db",
        repo_path / ".llmc" / "rag" / "index.db",
        repo_path / ".llmc" / "index_v2.db",
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return candidate
    
    return None


def main():
    if len(sys.argv) > 1:
        repo_path = Path(sys.argv[1]).resolve()
    else:
        repo_path = Path.cwd()
    
    if not repo_path.exists():
        print(f"Error: Path does not exist: {repo_path}")
        sys.exit(1)
    
    # Handle direct DB path
    if repo_path.suffix == ".db":
        analyze_database(repo_path)
        return
    
    db_path = find_rag_database(repo_path)
    if not db_path:
        print(f"Error: Could not find RAG database in {repo_path}")
        sys.exit(1)
    
    analyze_database(db_path)


if __name__ == "__main__":
    main()
