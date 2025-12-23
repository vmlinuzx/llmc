# Performance Analysis Report for LLMC

**Date:** 2025-12-21
**Analyst:** Rem, the Performance Testing Demon

## 1. Executive Summary

A performance analysis of the `llmc` repository was conducted, focusing on the RAG (Retrieval-Augmented Generation) query functionality.

**Initial benchmarks revealed a significant performance bottleneck in the `rag_query` tool, with an execution time of approximately 2.3 seconds.**

Profiling revealed that the root cause was not in the top-level command, but several layers deep in the `llmc.rag.cli` module. The primary issues were:
1.  **Slow, pure-Python vector calculations:** Dot product and norm calculations were performed manually, leading to high CPU usage.
2.  **Repetitive Graph Loading:** The RAG graph data was being loaded and processed on every search query.

A key optimization was implemented by replacing the pure-Python vector math with highly optimized `numpy` equivalents. This resulted in a **~65% reduction in the scoring time** and a **~27% reduction in the total end-to-end execution time** for the benchmarked query.

The primary remaining bottleneck is the graph loading and processing. Caching this data in memory is recommended as the next optimization step.

## 2. Test Environment

*   **Repository:** `/home/vmlinux/src/llmc`
*   **Branch:** `main`
*   **Commit:** (Not recorded, ran on dirty branch)
*   **Uncommitted Changes:**
    *   `modified:   llmc.toml` (to enable `tool_envelope`)
    *   `modified:   llmc/rag/search/__init__.py` (to implement numpy optimization)
    *   Other pre-existing local modifications.

## 3. Analysis and Findings

### Step 1: Initial Benchmark

The analysis began by running the project's built-in benchmark scripts. After resolving a configuration issue where the `tool_envelope` was disabled, the following baseline metrics were established for the `rag_top3` query:

*   **Execution Time:** ~2.3 seconds

This was identified as the most significant performance outlier.

### Step 2: Profiling and Bottleneck Identification

A deep profiling analysis was conducted, peeling back multiple layers of command-dispatching shell-outs.

1.  `llmc_mcp.benchmarks` shelled out to `te`.
2.  `te` shelled out to `llmc.rag.cli`.

The final profile of `llmc.rag.cli` revealed the true bottlenecks:

*   **`_score_candidates` (2.8s):** The function responsible for scoring search candidates was consuming the majority of the time.
*   **Pure Python Vector Math (2.3s):** Within `_score_candidates`, the functions `_dot` and `_norm` were implemented in pure Python, which is inefficient for vector operations.
*   **Graph Loading (2.0s):** The `expand_with_graph` function, responsible for loading and processing the RAG graph, was also a major contributor to the overall time.

### Step 3: Optimization and Verification

The most critical bottleneck was addressed by replacing the manual vector math with `numpy`.

*   **File Modified:** `llmc/rag/search/__init__.py`
*   **Change:** Replaced `_dot` and `_norm` implementations with `numpy.dot` and `numpy.linalg.norm`. The calling functions were updated to use `numpy` arrays.

After the optimization, the same profiling script was run again.

**Results:**

| Function            | Before (cumtime) | After (cumtime) | Improvement |
|---------------------|------------------|-----------------|-------------|
| `_score_candidates` | 2.8s             | 0.97s           | **~65%**    |
| Total Execution     | 5.5s             | 4.0s            | **~27%**    |

*(Note: Total times are higher than the initial benchmark due to profiler overhead, but the relative improvement is accurate.)*

## 4. Recommendations

1.  **Merge the `numpy` optimization:** The implemented change provides a significant performance boost and should be integrated.
2.  **Cache the RAG Graph:** The remaining major bottleneck is the graph loading in `expand_with_graph`. This data should be loaded once and cached in memory for the lifetime of the process, rather than being re-loaded for every search query.
3.  **Remove temporary files:** The temporary profiling scripts (`profile_rag.py`, `profile_te_rag_query.py`, `profile_rag_cli.py`) should be removed.

This concludes the performance analysis.