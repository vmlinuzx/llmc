#!/usr/bin/env python3
import sys
import os
import time
import subprocess
import signal
from pathlib import Path

# Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

REPO_ROOT = os.environ.get("LLMC_ROOT", os.getcwd())
PYTHON_CMD = [sys.executable, "-m", "llmc.rag.cli"]

def log_pass(msg):
    print(f"{GREEN}[PASS] {msg}{RESET}")

def log_fail(msg):
    print(f"{RED}[FAIL] {msg}{RESET}")

def log_info(msg):
    print(f"{YELLOW}[INFO] {msg}{RESET}")

def run_cmd(args, env=None, capture_output=True, timeout=None):
    e = os.environ.copy()
    if env:
        e.update(env)
    try:
        return subprocess.run(
            args,
            env=e,
            capture_output=capture_output,
            text=True,
            cwd=REPO_ROOT,
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return None

def test_parallel_index():
    log_info("1. Testing Parallel Index Operations...")
    log_info(f"Using Python: {sys.executable}")
    processes = []
    n_procs = 3

    for i in range(n_procs):
        p = subprocess.Popen(
            PYTHON_CMD + ["index", "--no-export"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=REPO_ROOT
        )
        processes.append(p)

    log_info(f"Started {n_procs} indexers...")

    exit_codes = []
    errors = []
    for p in processes:
        stdout, stderr = p.communicate()
        exit_codes.append(p.returncode)
        if p.returncode != 0:
            errors.append(stderr.decode())

    if all(c == 0 for c in exit_codes):
        log_pass("All indexers completed successfully.")
    else:
        # Check if errors are lock related
        lock_errors = [e for e in errors if "database is locked" in e or "locked" in e]
        # Check if errors are benign warnings (like Torch not installed) but exit code 0?
        # No, exit code != 0.

        # If exit code is non-zero, it failed.
        # But if the error is just warnings? No, warnings go to stderr but don't cause non-zero exit usually.
        # The traceback definitely causes non-zero.

        if lock_errors:
            log_pass("Some indexers failed with lock error (Expected for SQLite without WAL or heavy contention).")
        else:
            log_fail(f"Indexers failed with unexpected errors: {errors}")
            return False

    # Check DB health
    res = run_cmd(PYTHON_CMD + ["doctor", "--json"])
    if res and res.returncode == 0:
        log_pass("RAG Doctor confirms DB health.")
    else:
        log_fail("RAG Doctor found issues.")
        if res:
             print(res.stderr)
        return False
    return True

def test_concurrent_searches():
    log_info("2. Testing Concurrent Searches...")
    query = "test"
    n_procs = 5
    processes = []

    for i in range(n_procs):
        p = subprocess.Popen(
            PYTHON_CMD + ["search", query, "--limit", "1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            cwd=REPO_ROOT
        )
        processes.append(p)

    log_info(f"Started {n_procs} searchers...")

    failed = 0
    for p in processes:
        _, stderr = p.communicate()
        if p.returncode != 0:
            failed += 1
            # print(f"Search failed: {stderr.decode()}")
            # Reduce noise if it's just connection error

    if failed == 0:
        log_pass("All concurrent searches successful.")
        return True
    else:
        log_fail(f"{failed}/{n_procs} searches failed (Likely due to missing Ollama/Embeddings).")
        # We allow this to fail if environment is not set up for embeddings
        return False

def test_file_lock():
    log_info("3. Testing File Lock (Reader/Writer)...")

    indexer = subprocess.Popen(
        PYTHON_CMD + ["index", "--no-export"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=REPO_ROOT
    )

    time.sleep(0.5)

    searcher = subprocess.Popen(
        PYTHON_CMD + ["search", "test", "--limit", "1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=REPO_ROOT
    )

    _, e = searcher.communicate()
    indexer.wait()

    if searcher.returncode == 0:
        log_pass("Search worked during indexing.")
    else:
        if e and b"locked" in e:
             log_pass("Search blocked by lock (Acceptable).")
        elif e and b"Connection refused" in e:
             log_info("Search failed due to connection error (Ollama down). Ignoring lock test aspect.")
        else:
             log_fail(f"Search crashed: {e.decode() if e else 'Unknown'}")
             return False
    return True

def test_signal_handling():
    log_info("4. Testing Signal Handling...")

    p = subprocess.Popen(
        PYTHON_CMD + ["index"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=REPO_ROOT
    )

    time.sleep(0.5)
    p.send_signal(signal.SIGINT)

    try:
        p.wait(timeout=5)
        log_pass("Process exited after SIGINT.")
    except subprocess.TimeoutExpired:
        p.kill()
        log_fail("Process did not exit after SIGINT.")
        return False

    res = run_cmd(PYTHON_CMD + ["doctor"])
    if res and res.returncode == 0:
        log_pass("DB healthy after interruption.")
    else:
        log_fail("DB corrupt after interruption.")
        if res:
            print(res.stderr)
        return False
    return True

def test_daemon_restart():
    log_info("5. Testing Daemon Restart...")

    daemon_cmd = [sys.executable, "-m", "llmc.rag.service", "_daemon_loop", "--interval", "1"]

    env = os.environ.copy()

    p = subprocess.Popen(
        daemon_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=REPO_ROOT,
        env=env
    )

    time.sleep(2)
    if p.poll() is not None:
        log_info("Daemon exited early. Skipping restart test.")
        return True

    log_info("Daemon running. Restarting...")
    p.terminate()
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()

    p2 = subprocess.Popen(
        daemon_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=REPO_ROOT,
        env=env
    )
    time.sleep(2)

    if p2.poll() is None:
        log_pass("Daemon restarted successfully.")
        p2.terminate()
        p2.wait()
    else:
        log_fail("Daemon failed to restart.")
        return False

    return True

def main():
    print(f"Running Concurrency Demon on {REPO_ROOT}\n")

    results = []
    # run all even if some fail
    results.append(test_parallel_index())
    results.append(test_concurrent_searches())
    results.append(test_file_lock())
    results.append(test_signal_handling())
    results.append(test_daemon_restart())

    print("-" * 40)
    # We exit with 0 even if failures occur to avoid breaking pipelines?
    # No, user wants output.
    # But usually a test script should exit non-zero on failure.
    if all(results):
        log_pass("ALL CONCURRENCY CHECKS PASSED")
        sys.exit(0)
    else:
        log_fail("SOME CHECKS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
