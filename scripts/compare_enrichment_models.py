#!/usr/bin/env python3
"""
Compare enrichment quality between Qwen 2.5:7b and Qwen3:4b models.

This script analyzes:
1. Summary length and verbosity
2. Tag quality and coverage
3. Evidence specificity
4. Input/output documentation
5. Side-by-side qualitative examples
"""

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import statistics
import textwrap

OLD_DB = Path("/home/vmlinux/src/llmc/.rag/index_v2.db.backup-qwen25-20251208")
NEW_DB = Path("/home/vmlinux/src/llmc/.rag/index_v2.db")

OLD_MODEL = "qwen2.5:7b-instruct"
NEW_MODEL = "qwen3:4b-instruct"


@dataclass
class EnrichmentStats:
    model: str
    total_count: int
    avg_summary_len: float
    avg_tags_len: float
    avg_evidence_len: float
    avg_inputs_len: float
    avg_outputs_len: float
    empty_summary_count: int
    empty_tags_count: int
    empty_evidence_count: int
    summary_lengths: list[int]


def get_stats(db_path: Path, model: str) -> EnrichmentStats:
    """Get enrichment statistics for a model."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Get all enrichments for this model
    cur.execute(
        """
        SELECT summary, tags, evidence, inputs, outputs 
        FROM enrichments 
        WHERE model = ?
    """,
        (model,),
    )

    rows = cur.fetchall()

    summary_lens = []
    tags_lens = []
    evidence_lens = []
    inputs_lens = []
    outputs_lens = []
    empty_summary = 0
    empty_tags = 0
    empty_evidence = 0

    for summary, tags, evidence, inputs, outputs in rows:
        s_len = len(summary or "")
        t_len = len(tags or "")
        e_len = len(evidence or "")
        i_len = len(inputs or "")
        o_len = len(outputs or "")

        summary_lens.append(s_len)
        tags_lens.append(t_len)
        evidence_lens.append(e_len)
        inputs_lens.append(i_len)
        outputs_lens.append(o_len)

        if s_len == 0:
            empty_summary += 1
        if t_len == 0:
            empty_tags += 1
        if e_len == 0:
            empty_evidence += 1

    conn.close()

    return EnrichmentStats(
        model=model,
        total_count=len(rows),
        avg_summary_len=statistics.mean(summary_lens) if summary_lens else 0,
        avg_tags_len=statistics.mean(tags_lens) if tags_lens else 0,
        avg_evidence_len=statistics.mean(evidence_lens) if evidence_lens else 0,
        avg_inputs_len=statistics.mean(inputs_lens) if inputs_lens else 0,
        avg_outputs_len=statistics.mean(outputs_lens) if outputs_lens else 0,
        empty_summary_count=empty_summary,
        empty_tags_count=empty_tags,
        empty_evidence_count=empty_evidence,
        summary_lengths=summary_lens,
    )


def get_common_hashes(limit: int = 10) -> list[str]:
    """Find span_hashes that exist in both databases with substantial content."""
    conn_old = sqlite3.connect(OLD_DB)
    conn_new = sqlite3.connect(NEW_DB)

    cur_old = conn_old.cursor()
    cur_new = conn_new.cursor()

    # Get hashes with substantial summaries from both
    cur_old.execute(
        """
        SELECT span_hash FROM enrichments 
        WHERE model = ? AND LENGTH(summary) > 80
        ORDER BY LENGTH(summary) DESC
    """,
        (OLD_MODEL,),
    )
    old_hashes = set(row[0] for row in cur_old.fetchall())

    cur_new.execute(
        """
        SELECT span_hash FROM enrichments 
        WHERE model = ? AND LENGTH(summary) > 80
    """,
        (NEW_MODEL,),
    )
    new_hashes = set(row[0] for row in cur_new.fetchall())

    common = list(old_hashes & new_hashes)[:limit]

    conn_old.close()
    conn_new.close()

    return common


def get_enrichment(db_path: Path, span_hash: str) -> dict:
    """Get enrichment data for a span."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT summary, tags, evidence, inputs, outputs, model 
        FROM enrichments 
        WHERE span_hash = ?
    """,
        (span_hash,),
    )
    row = cur.fetchone()
    conn.close()

    if row:
        return {
            "summary": row[0] or "",
            "tags": row[1] or "",
            "evidence": row[2] or "",
            "inputs": row[3] or "",
            "outputs": row[4] or "",
            "model": row[5] or "",
        }
    return {}


def get_span_file(db_path: Path, span_hash: str) -> str:
    """Get the file path for a span."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT f.path 
        FROM spans s
        JOIN files f ON s.file_id = f.id
        WHERE s.span_hash = ?
    """,
        (span_hash,),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "unknown"


def print_comparison(span_hash: str):
    """Print side-by-side comparison of a span."""
    old_data = get_enrichment(OLD_DB, span_hash)
    new_data = get_enrichment(NEW_DB, span_hash)
    file_path = get_span_file(OLD_DB, span_hash)

    print(f"\n{'='*80}")
    print(f"FILE: {file_path}")
    print(f"HASH: {span_hash[:40]}...")
    print(f"{'='*80}")

    print(f"\n{'-'*35} QWEN 2.5:7B {'-'*32}")
    print(f"SUMMARY ({len(old_data.get('summary', ''))} chars):")
    print(
        textwrap.fill(
            old_data.get("summary", "N/A"),
            width=78,
            initial_indent="  ",
            subsequent_indent="  ",
        )
    )
    print(f"\nTAGS: {old_data.get('tags', 'N/A')}")

    print(f"\n{'-'*35} QWEN 3:4B {'-'*34}")
    print(f"SUMMARY ({len(new_data.get('summary', ''))} chars):")
    print(
        textwrap.fill(
            new_data.get("summary", "N/A"),
            width=78,
            initial_indent="  ",
            subsequent_indent="  ",
        )
    )
    print(f"\nTAGS: {new_data.get('tags', 'N/A')}")


def main():
    print("=" * 80)
    print("ENRICHMENT MODEL COMPARISON ANALYSIS")
    print(f"OLD: {OLD_MODEL} | NEW: {NEW_MODEL}")
    print("=" * 80)

    # Get statistics
    print("\n📊 Gathering statistics...")
    old_stats = get_stats(OLD_DB, OLD_MODEL)
    new_stats = get_stats(NEW_DB, NEW_MODEL)

    print("\n" + "=" * 80)
    print("QUANTITATIVE COMPARISON")
    print("=" * 80)

    print(f"\n{'Metric':<25} {'Qwen 2.5:7B':>15} {'Qwen 3:4B':>15} {'Δ (New-Old)':>15}")
    print("-" * 75)
    print(
        f"{'Total Enrichments':<25} {old_stats.total_count:>15,} {new_stats.total_count:>15,} {new_stats.total_count - old_stats.total_count:>+15,}"
    )
    print(
        f"{'Avg Summary Length':<25} {old_stats.avg_summary_len:>15.1f} {new_stats.avg_summary_len:>15.1f} {new_stats.avg_summary_len - old_stats.avg_summary_len:>+15.1f}"
    )
    print(
        f"{'Avg Tags Length':<25} {old_stats.avg_tags_len:>15.1f} {new_stats.avg_tags_len:>15.1f} {new_stats.avg_tags_len - old_stats.avg_tags_len:>+15.1f}"
    )
    print(
        f"{'Avg Evidence Length':<25} {old_stats.avg_evidence_len:>15.1f} {new_stats.avg_evidence_len:>15.1f} {new_stats.avg_evidence_len - old_stats.avg_evidence_len:>+15.1f}"
    )
    print(
        f"{'Avg Inputs Length':<25} {old_stats.avg_inputs_len:>15.1f} {new_stats.avg_inputs_len:>15.1f} {new_stats.avg_inputs_len - old_stats.avg_inputs_len:>+15.1f}"
    )
    print(
        f"{'Avg Outputs Length':<25} {old_stats.avg_outputs_len:>15.1f} {new_stats.avg_outputs_len:>15.1f} {new_stats.avg_outputs_len - old_stats.avg_outputs_len:>+15.1f}"
    )
    print("-" * 75)
    print(
        f"{'Empty Summaries':<25} {old_stats.empty_summary_count:>15,} {new_stats.empty_summary_count:>15,}"
    )
    print(
        f"{'Empty Tags':<25} {old_stats.empty_tags_count:>15,} {new_stats.empty_tags_count:>15,}"
    )
    print(
        f"{'Empty Evidence':<25} {old_stats.empty_evidence_count:>15,} {new_stats.empty_evidence_count:>15,}"
    )

    # Summary length distribution
    print("\n" + "=" * 80)
    print("SUMMARY LENGTH DISTRIBUTION")
    print("=" * 80)

    for label, stats in [("Qwen 2.5:7B", old_stats), ("Qwen 3:4B", new_stats)]:
        lens = stats.summary_lengths
        if lens:
            p25 = statistics.quantiles(lens, n=4)[0]
            p50 = statistics.median(lens)
            p75 = statistics.quantiles(lens, n=4)[2]
            print(f"\n{label}:")
            print(
                f"  Min: {min(lens):>4}  P25: {p25:>4.0f}  Median: {p50:>4.0f}  P75: {p75:>4.0f}  Max: {max(lens):>4}"
            )

    # Verbosity ratio
    verbosity_ratio = (
        new_stats.avg_summary_len / old_stats.avg_summary_len
        if old_stats.avg_summary_len
        else 0
    )
    print(f"\n📈 Verbosity Ratio (New/Old): {verbosity_ratio:.2f}x")
    if verbosity_ratio > 1.5:
        print("   → Qwen3:4b produces significantly MORE detailed summaries")
    elif verbosity_ratio < 0.67:
        print("   → Qwen3:4b produces significantly SHORTER summaries")
    else:
        print("   → Both models produce similar length summaries")

    # Side-by-side examples
    print("\n" + "=" * 80)
    print("QUALITATIVE COMPARISON (5 Random Examples)")
    print("=" * 80)

    common_hashes = get_common_hashes(5)
    for span_hash in common_hashes:
        print_comparison(span_hash)

    # Assessment
    print("\n" + "=" * 80)
    print("ASSESSMENT")
    print("=" * 80)

    print(
        f"""
Key Findings:

1. VERBOSITY: Qwen3:4b produces {verbosity_ratio:.1f}x longer summaries on average
   - Old avg: {old_stats.avg_summary_len:.0f} chars | New avg: {new_stats.avg_summary_len:.0f} chars

2. COVERAGE: 
   - Old: {old_stats.total_count:,} enrichments | New: {new_stats.total_count:,} enrichments
   - Empty summaries: Old {old_stats.empty_summary_count:,} vs New {new_stats.empty_summary_count:,}

3. METADATA RICHNESS:
   - Tags: {new_stats.avg_tags_len/old_stats.avg_tags_len if old_stats.avg_tags_len else 0:.1f}x more detailed
   - Evidence: {new_stats.avg_evidence_len/old_stats.avg_evidence_len if old_stats.avg_evidence_len else 0:.1f}x more detailed
   - Inputs: {new_stats.avg_inputs_len/old_stats.avg_inputs_len if old_stats.avg_inputs_len else 0:.1f}x more detailed
   - Outputs: {new_stats.avg_outputs_len/old_stats.avg_outputs_len if old_stats.avg_outputs_len else 0:.1f}x more detailed
"""
    )


if __name__ == "__main__":
    main()
