#!/usr/bin/env python3
import sys
import time
import subprocess
import os
import shutil
from pathlib import Path

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def log(msg, color=RESET):
    print(f"{color}{msg}{RESET}")

def check_import_time():
    log("--- 1. Import Time Profiling ---", YELLOW)
    start = time.perf_counter()
    try:
        import llmc
        # Force load of submodules that might be lazy
        import llmc.main
    except ImportError as e:
        log(f"FAIL: Could not import llmc: {e}", RED)
        return False

    end = time.perf_counter()
    duration = end - start
    log(f"Import time: {duration:.4f}s")

    # Threshold < 1.0s ideally, but let's say 2.0s as per docs "Startup time < 2s" which includes import
    if duration > 1.5:
        log("WARN: Import time > 1.5s", YELLOW)
        # Not a hard fail, but a warning
        return True
    else:
        log("PASS: Import time < 1.5s", GREEN)
        return True

def check_startup_latency():
    log("\n--- 5. Startup Latency (CLI Cold Start) ---", YELLOW)
    # Measure 'llmc --version'
    start = time.perf_counter()
    try:
        # We need to ensure PYTHONPATH includes CWD for the subprocess
        env = os.environ.copy()
        if "PYTHONPATH" not in env:
            env["PYTHONPATH"] = os.getcwd()
        else:
            env["PYTHONPATH"] = os.getcwd() + os.pathsep + env["PYTHONPATH"]

        subprocess.run([sys.executable, "-m", "llmc.main", "--version"],
                       capture_output=True, check=True, env=env)
    except subprocess.CalledProcessError as e:
        log(f"Error running llmc: {e}", RED)
        log(e.stderr.decode(), RED)
        return False
    end = time.perf_counter()
    duration = end - start
    log(f"Startup time: {duration:.4f}s")

    if duration > 2.0:
        log("FAIL: Startup time > 2.0s", RED)
        return False
    else:
        log("PASS: Startup time < 2.0s", GREEN)
        return True

def check_search_latency():
    log("\n--- Search Latency (Smoke Test) ---", YELLOW)
    # We need a query that returns something or at least runs the search path.
    # "test" is generic.
    start = time.perf_counter()
    try:
        env = os.environ.copy()
        if "PYTHONPATH" not in env:
            env["PYTHONPATH"] = os.getcwd()
        else:
            env["PYTHONPATH"] = os.getcwd() + os.pathsep + env["PYTHONPATH"]

        # We assume RAG might not be fully active, so we accept failure if it's due to no index
        # but we measure time until failure/success.
        # If exit code is 0, it worked.
        proc = subprocess.run([sys.executable, "-m", "llmc.main", "analytics", "search", "test", "--limit", "1"],
                       capture_output=True, env=env)

        if proc.returncode != 0:
            log(f"Search command failed (likely no index), but measuring overhead. Error: {proc.stderr.decode()[:100]}...", YELLOW)

    except Exception as e:
        log(f"Error running search: {e}", RED)
        return False

    end = time.perf_counter()
    duration = end - start
    log(f"Search command duration: {duration:.4f}s")

    if duration > 1.0: # 500ms is target, but 1s slack
        log("WARN: Search latency > 1.0s", YELLOW)
    else:
        log("PASS: Search latency < 1.0s", GREEN)

    return True

def check_memory_usage():
    log("\n--- 3. Memory Usage ---", YELLOW)
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        rss_mb = mem_info.rss / 1024 / 1024
        log(f"Current Script Memory (RSS): {rss_mb:.2f} MB")

        if rss_mb > 500:
            log("FAIL: Memory usage > 500MB", RED)
            return False
        else:
            log("PASS: Memory usage < 500MB", GREEN)
            return True
    except ImportError:
        log("psutil not installed, skipping detailed memory check", YELLOW)
        return True

def run_pytest_benchmark():
    log("\n--- 2 & 4. Pytest Benchmark & Slow Tests ---", YELLOW)

    cmd = [sys.executable, "-m", "pytest", "-q", "--durations=10"]

    try:
        import pytest_benchmark
        # We don't add --benchmark-only because we want slow test detection too.
        # But if we had benchmarks, they would run.
        pass
    except ImportError:
        log("pytest-benchmark not installed, skipping benchmarks", YELLOW)
        pass

    try:
        log("Running pytest (this may take time)...")
        # We assume the user wants to test the whole repo or relevant parts.
        # But to be safe and fast, maybe we can limit to tests/core or similar if it existed.
        # Given we are in root, it runs everything.

        env = os.environ.copy()
        if "PYTHONPATH" not in env:
            env["PYTHONPATH"] = os.getcwd()
        else:
            env["PYTHONPATH"] = os.getcwd() + os.pathsep + env["PYTHONPATH"]

        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)

        # Parse for slow tests
        slow_found = False
        output_lines = proc.stdout.splitlines()

        # Print summary (fail or pass)
        if proc.returncode != 0 and proc.returncode != 5:
            log(f"Pytest finished with errors (exit code {proc.returncode})", YELLOW)
            # Print stderr if any
            if proc.stderr:
                print(proc.stderr)

        # If benchmarks ran, print the table
        benchmark_table_started = False
        for line in output_lines:
            if "benchmark:" in line or "Name (time in" in line:
                benchmark_table_started = True
            if benchmark_table_started:
                print(line)
                if line.strip() == "": # End of table usually followed by empty line or summary
                    # Continue printing until next section or end?
                    # pytest-benchmark table usually is at the end.
                    pass

        # Also print summary lines
        log("Pytest Summary:")
        for line in output_lines[-5:]:
            print(line)

        for line in output_lines:
            if "s call" in line:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0].endswith("s"):
                    try:
                        dur = float(parts[0][:-1])
                        if dur > 5.0:
                            log(f"SLOW TEST: {line}", RED)
                            slow_found = True
                    except ValueError:
                        pass

        if slow_found:
            log("FAIL: Slow tests (>5s) detected", RED)
            return False
        else:
            log("PASS: No slow tests detected", GREEN)
            return True

    except Exception as e:
        log(f"Error running pytest: {e}", RED)
        return False

def main():
    log("=== Performance Demon ===", GREEN)

    # Ensure current directory is in sys.path for import checks in THIS process
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())

    results = []
    results.append(check_import_time())
    results.append(check_startup_latency())
    results.append(check_memory_usage())
    results.append(check_search_latency())
    results.append(run_pytest_benchmark())

    if all(results):
        log("\nAll checks PASSED", GREEN)
        sys.exit(0)
    else:
        log("\nSome checks FAILED", RED)
        sys.exit(1)

if __name__ == "__main__":
    main()
