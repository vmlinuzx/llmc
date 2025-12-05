#!/usr/bin/env python3
"""
Ruthless Test Analysis Tool
Analyzes test failures across the entire test suite
"""

import glob
import json
from pathlib import Path
import subprocess


def run_test_batch(test_pattern, output_file):
    """Run a batch of tests and capture results"""
    print(f"\n{'=' * 80}")
    print(f"Testing: {test_pattern}")
    print(f"{'=' * 80}")

    test_files = glob.glob(test_pattern)
    if not test_files:
        print(f"No files found for pattern: {test_pattern}")
        return {"pattern": test_pattern, "failed": 0, "passed": 0, "failures": [], "error_count": 0}

    cmd = [
        "python3",
        "-m",
        "pytest",
        *test_files,  # Pass expanded files
        "-v",
        "--tb=line",
        "-q",
    ]

    result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=120)

    # Parse output
    lines = result.stdout.split("\n") + result.stderr.split("\n")

    failures = []
    passed = 0
    failed = 0

    for line in lines:
        if "FAILED" in line and "::" in line:
            failures.append(line.strip())
        elif "passed" in line.lower() and "in " in line.lower():
            # Parse summary line like "=== 22 failed, 8 passed in 0.61s ==="
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "failed," and i > 0:
                    failed = int(parts[i - 1])
                elif part == "passed" and i > 0 and parts[i - 1] != "failed,":
                    passed = int(parts[i - 1])

    return {
        "pattern": test_pattern,
        "failed": failed,
        "passed": passed,
        "failures": failures[:20],  # Limit to first 20 failures
        "error_count": len(failures),
    }


def analyze_failures(all_results):
    """Analyze failure patterns across test batches"""
    print("\n" + "=" * 80)
    print("FAILURE ANALYSIS SUMMARY")
    print("=" * 80)

    total_failed = sum(r["failed"] for r in all_results)
    total_passed = sum(r["passed"] for r in all_results)

    print(f"\nTOTAL: {total_failed} failed, {total_passed} passed")
    print(f"Success Rate: {(total_passed / (total_failed + total_passed) * 100):.1f}%\n")

    # Categorize failures
    categories = {
        "gateway_import": [],
        "graph_stitching": [],
        "rag_analytics": [],
        "rag_daemon": [],
        "repo": [],
        "enrichment": [],
        "other": [],
    }

    for result in all_results:
        for failure in result["failures"]:
            failure_lower = failure.lower()
            if "gateway" in failure_lower:
                categories["gateway_import"].append(failure)
            elif "stitch" in failure_lower:
                categories["graph_stitching"].append(failure)
            elif "analytics" in failure_lower:
                categories["rag_analytics"].append(failure)
            elif "daemon" in failure_lower:
                categories["rag_daemon"].append(failure)
            elif "repo" in failure_lower:
                categories["repo"].append(failure)
            elif "enrichment" in failure_lower:
                categories["enrichment"].append(failure)
            else:
                categories["other"].append(failure)

    for category, failures in categories.items():
        if failures:
            print(f"\n{category.upper()} ({len(failures)} failures):")
            for failure in failures[:10]:
                print(f"  - {failure}")

    return categories


def main():
    test_batches = [
        "tests/test_graph_*.py",
        "tests/test_rag_nav_*.py",
        "tests/test_rag_*.py",
        "tests/test_enrichment_*.py",
        "tests/test_context_gateway*.py",
        "tests/test_e2e_*.py",
        "tests/test_router*.py",
    ]

    results = []
    for batch in test_batches:
        try:
            result = run_test_batch(batch, f"/tmp/test_{batch.replace('/', '_')}.json")
            results.append(result)
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT: {batch}")
        except Exception as e:
            print(f"ERROR running {batch}: {e}")

    categories = analyze_failures(results)

    # Save detailed report
    report = {
        "summary": {
            "total_batches": len(results),
            "total_failed": sum(r["failed"] for r in results),
            "total_passed": sum(r["passed"] for r in results),
        },
        "by_batch": results,
        "by_category": categories,
    }

    with open(Path(__file__).parent / "ruthless_test_analysis.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n\nDetailed report saved to: {Path(__file__).parent / 'ruthless_test_analysis.json'}")


if __name__ == "__main__":
    main()
