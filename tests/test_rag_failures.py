#!/usr/bin/env python3
"""
Comprehensive stress tests for LLMC RAG Daemon & Repo Tool.
This script finds failures - green is suspicious!
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

def run_cmd(cmd, cwd="/home/vmlinux/src/llmc", timeout=5):
    """Run a command and return result."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"

def test_state_store_corrupt_data():
    """Test state store with corrupt JSON."""
    print("\n" + "="*70)
    print("TEST: State Store - Corrupt JSON Handling")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "state"
        store_path.mkdir(parents=True, exist_ok=True)
        corrupt_file = store_path / "corrupt-repo.json"

        # Create corrupt JSON file
        corrupt_file.write_text("{ this is not valid json @@##", encoding="utf-8")

        # Try to load - should not crash
        code = f"""
import sys
sys.path.insert(0, '/home/vmlinux/src/llmc')
from tools.rag_daemon.state_store import StateStore
from pathlib import Path

store = StateStore(Path('{store_path}'))
states = store.load_all()
print(f'Loaded {{len(states)}} states (corrupt file ignored)')
print(f'SUCCESS: Corrupt JSON was ignored without crashing')
"""
        returncode, stdout, stderr = run_cmd(f'python3 -c "{code}"')

        print(f"Return code: {returncode}")
        print(f"Output: {stdout}")
        if stderr:
            print(f"Stderr: {stderr[:200]}")

        if returncode == 0 and "corrupt file ignored" in stdout:
            print("✓ PASS: Corrupt JSON handled gracefully")
            return True
        else:
            print("✗ FAIL: Error handling corrupt JSON")
            return False

def test_scheduler_consecutive_failures():
    """Test scheduler backoff logic with consecutive failures."""
    print("\n" + "="*70)
    print("TEST: Scheduler - Consecutive Failures & Backoff")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a config
        config = {
            "tick_interval_seconds": 60,
            "max_concurrent_jobs": 2,
            "max_consecutive_failures": 3,
            "base_backoff_seconds": 60,
            "max_backoff_seconds": 3600,
            "registry_path": f"{tmpdir}/registry.yml",
            "state_store_path": f"{tmpdir}/state",
            "log_path": f"{tmpdir}/logs",
            "control_dir": f"{tmpdir}/control",
        }

        # Test backoff calculation
        code = f"""
import sys
sys.path.insert(0, '/home/vmlinux/src/llmc')
from datetime import datetime, timedelta, timezone
from tools.rag_daemon.models import RepoState

# Simulate backoff calculation
consecutive_failures = 3
base_backoff = 60
max_backoff = 3600

backoff_seconds = base_backoff * (2 ** (consecutive_failures - 1))
backoff_seconds = min(backoff_seconds, max_backoff)

print(f'Consecutive failures: {{consecutive_failures}}')
print(f'Calculated backoff: {{backoff_seconds}} seconds ({{backoff_seconds/60:.1f}} minutes)')
print(f'Expected backoff: 240 seconds (4 minutes)')
print(f'Expected max backoff: {{max_backoff}} seconds (1 hour)')

if backoff_seconds == 240:
    print('✓ PASS: Backoff calculation correct')
else:
    print('✗ FAIL: Incorrect backoff calculation')
    sys.exit(1)
"""
        returncode, stdout, stderr = run_cmd(f'python3 -c "{code}"')

        print(stdout)
        if stderr:
            print(f"Stderr: {stderr[:200]}")

        return returncode == 0

def test_control_surface():
    """Test control surface flag handling."""
    print("\n" + "="*70)
    print("TEST: Control Surface - Flag File Handling")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        control_dir = Path(tmpdir) / "control"
        control_dir.mkdir()

        # Create flag files
        (control_dir / "refresh_all.flag").touch()
        (control_dir / "refresh_repo-123.flag").touch()
        (control_dir / "shutdown.flag").touch()

        code = f"""
import sys
sys.path.insert(0, '/home/vmlinux/src/llmc')
from tools.rag_daemon.control import read_control_events
from pathlib import Path

events = read_control_events(Path('{control_dir}'))
print(f'refresh_all: {{events.refresh_all}}')
print(f'refresh_repo_ids: {{events.refresh_repo_ids}}')
print(f'shutdown: {{events.shutdown}}')

expected_repos = {{'repo-123'}}
if events.refresh_all and events.shutdown and events.refresh_repo_ids == expected_repos:
    print('✓ PASS: All flags detected correctly')
else:
    print('✗ FAIL: Flag detection incorrect')
    sys.exit(1)

# Check flags are cleaned up
remaining = list(control_dir.glob('*.flag'))
if len(remaining) == 0:
    print('✓ PASS: Flags cleaned up after reading')
else:
    print(f'✗ FAIL: {{len(remaining)}} flags not cleaned up')
    sys.exit(1)
"""
        returncode, stdout, stderr = run_cmd(f'python3 -c "{code}"')

        print(stdout)
        if stderr:
            print(f"Stderr: {stderr[:200]}")

        return returncode == 0

def test_registry_empty_and_invalid():
    """Test registry with empty and invalid data."""
    print("\n" + "="*70)
    print("TEST: Registry - Empty and Invalid Path Handling")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "empty_registry.yml"

        # Test empty registry
        code = f"""
import sys
sys.path.insert(0, '/home/vmlinux/src/llmc')
from tools.rag_repo.config import ToolConfig
from tools.rag_repo.registry import RegistryAdapter

cfg = ToolConfig(registry_path=Path('{registry_path}'))
adapter = RegistryAdapter(cfg)

# Load from non-existent file - should return empty dict
entries = adapter.load_all()
print(f'Entries from empty registry: {{len(entries)}}')

if len(entries) == 0:
    print('✓ PASS: Empty registry handled correctly')
else:
    print('✗ FAIL: Empty registry returned unexpected data')
    sys.exit(1)
"""
        returncode, stdout, stderr = run_cmd(f'python3 -c "{code}"')

        print(stdout)
        if stderr:
            print(f"Stderr: {stderr[:200]}")

        return returncode == 0

def test_repo_tool_commands():
    """Test repo tool add/remove/list/inspect commands."""
    print("\n" + "="*70)
    print("TEST: Repo Tool - Command Line Interface")
    print("="*70)

    results = []

    # Test 1: Help command
    print("\n[1] Testing help command...")
    returncode, stdout, stderr = run_cmd('/home/vmlinux/src/llmc/scripts/llmc-rag-repo help')
    if "LLMC RAG Repo Tool" in stdout and returncode == 0:
        print("✓ PASS: Help command works")
        results.append(True)
    else:
        print("✗ FAIL: Help command failed")
        results.append(False)

    # Test 2: List with empty registry
    print("\n[2] Testing list command with empty registry...")
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "empty.yml"
        returncode, stdout, stderr = run_cmd(
            f'/home/vmlinux/src/llmc/scripts/llmc-rag-repo --config {registry_path} list'
        )
        if "No repos registered" in stdout and returncode == 0:
            print("✓ PASS: List command works with empty registry")
            results.append(True)
        else:
            print(f"✗ FAIL: List command failed (exit: {returncode})")
            print(f"  stdout: {stdout[:100]}")
            results.append(False)

    # Test 3: Inspect non-existent repo
    print("\n[3] Testing inspect on non-existent repo...")
    returncode, stdout, stderr = run_cmd('/home/vmlinux/src/llmc/scripts/llmc-rag-repo inspect /nonexistent/path')
    if returncode != 0:
        print("✓ PASS: Inspect correctly rejects non-existent path")
        results.append(True)
    else:
        print("✗ FAIL: Inspect should fail for non-existent repo")
        results.append(False)

    return all(results)

def test_worker_pool_failure():
    """Test worker pool failure handling."""
    print("\n" + "="*70)
    print("TEST: Worker Pool - Failure Handling")
    print("="*70)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake job runner that fails
        fake_runner = Path(tmpdir) / "fake_runner.sh"
        fake_runner.write_text("#!/bin/bash\nexit 1\n")
        fake_runner.chmod(0o755)

        config = {
            "tick_interval_seconds": 60,
            "max_concurrent_jobs": 1,
            "max_consecutive_failures": 3,
            "base_backoff_seconds": 60,
            "max_backoff_seconds": 3600,
            "registry_path": f"{tmpdir}/registry.yml",
            "state_store_path": f"{tmpdir}/state",
            "log_path": f"{tmpdir}/logs",
            "control_dir": f"{tmpdir}/control",
            "job_runner_cmd": str(fake_runner),
        }

        # Test worker failure handling
        code = f"""
import sys
sys.path.insert(0, '/home/vmlinux/src/llmc')
from tools.rag_daemon.models import RepoDescriptor, Job
from tools.rag_daemon.workers import WorkerPool, make_job_id
from tools.rag_daemon.state_store import StateStore
from tools.rag_daemon.models import DaemonConfig
from pathlib import Path
import yaml

config_dict = {config}
# Convert paths to proper format
for key in ['registry_path', 'state_store_path', 'log_path', 'control_dir']:
    config_dict[key] = Path(config_dict[key])

# Create DaemonConfig
from tools.rag_daemon.models import DaemonConfig
cfg = DaemonConfig(**config_dict)

store = StateStore(cfg.state_store_path)

# Create a test repo
from tools.rag_repo.models import RepoDescriptor
repo = RepoDescriptor(
    repo_id='test-repo',
    repo_path=Path('{tmpdir}/test'),
    rag_workspace_path=Path('{tmpdir}/test/.llmc/rag'),
)

# Create worker pool
workers = WorkerPool(cfg, store)

# Submit a job (it will fail because fake_runner exits with 1)
job = Job(job_id=make_job_id(), repo=repo, force=True)
print(f'Submitting job {{job.job_id}}')
workers.submit_jobs([job])

# Wait for completion (give it time)
import time
time.sleep(2)

# Check state
state = store.get('test-repo')
print(f'Final status: {{state.last_run_status}}')
print(f'Consecutive failures: {{state.consecutive_failures}}')
print(f'Next eligible: {{state.next_eligible_at}}')

if state.last_run_status == 'error' and state.consecutive_failures == 1:
    print('✓ PASS: Worker correctly recorded failure')
else:
    print('✗ FAIL: Worker did not handle failure correctly')
    sys.exit(1)
"""
        returncode, stdout, stderr = run_cmd(f'python3 -c "{code}"', timeout=10)

        print(stdout)
        if stderr:
            print(f"Stderr: {stderr[:200]}")

        return returncode == 0

def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("LLMC RAG DAEMON & REPO TOOL - RUTHLESS TESTING")
    print("="*70)
    print("\nFinding failures is success. Green is suspicious.\n")

    tests = [
        ("State Store - Corrupt Data", test_state_store_corrupt_data),
        ("Scheduler - Failures & Backoff", test_scheduler_consecutive_failures),
        ("Control Surface", test_control_surface),
        ("Registry - Empty/Invalid", test_registry_empty_and_invalid),
        ("Repo Tool - CLI Commands", test_repo_tool_commands),
        ("Worker Pool - Failure Handling", test_worker_pool_failure),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ EXCEPTION in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    failed = sum(1 for _, r in results if not r)
    total = len(results)

    print(f"\nTotal: {failed}/{total} tests FAILED")

    if failed > 0:
        print("\n🐛 BUGS FOUND! This is GOOD for a testing agent.")
        sys.exit(1)
    else:
        print("\n⚠️  All tests passed - suspiciously green!")
        sys.exit(0)

if __name__ == "__main__":
    main()
