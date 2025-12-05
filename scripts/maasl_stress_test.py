#!/usr/bin/env python3
"""
MAASL Multi-Agent Stress Test

Simulates N concurrent agents performing various operations to test
the Multi-Agent Anti-Stomp Layer (MAASL) under realistic load.

Usage:
    python3 scripts/maasl_stress_test.py --agents 5 --duration 60
    python3 scripts/maasl_stress_test.py --scenario concurrent_files
"""

import argparse
from pathlib import Path
import queue
import random
import sys
import tempfile
import threading
import time

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llmc_mcp.maasl import ResourceDescriptor, get_maasl


class AgentSimulator:
    """Simulates a single agent performing operations."""
    
    def __init__(self, agent_id: int, work_dir: Path):
        self.agent_id = agent_id
        self.work_dir = work_dir
        self.operations_completed = 0
        self.errors = []
        self.lock_waits = []
    
    def run_file_edit_workload(self, duration_sec: int):
        """Edit files concurrently with other agents."""
        end_time = time.time() + duration_sec
        test_files = [self.work_dir / f"agent_{self.agent_id}_file_{i}.py" 
                      for i in range(3)]
        
        # Create initial files
        for f in test_files:
            f.write_text(f"# Agent {self.agent_id} initial content\nvalue = 0\n")
        
        while time.time() < end_time:
            target_file = random.choice(test_files)
            
            try:
                start = time.time()
                
                # Simulate file edit with MAASL protection
                def edit_file():
                    content = target_file.read_text()
                    lines = content.split('\n')
                    # Increment value
                    for i, line in enumerate(lines):
                        if line.startswith('value ='):
                            current = int(line.split('=')[1].strip())
                            lines[i] = f'value = {current + 1}'
                    target_file.write_text('\n'.join(lines))
                    return True
                
                result = get_maasl().call_with_stomp_guard(
                    op=edit_file,
                    resources=[ResourceDescriptor('CRIT_CODE', str(target_file))],
                    intent="edit_file",
                    mode="interactive",
                    agent_id=str(self.agent_id),
                    session_id=f"session_{self.agent_id}"
                )
                
                wait_time = time.time() - start
                self.lock_waits.append(wait_time * 1000)  # Convert to ms
                
                if result:
                    self.operations_completed += 1
                
            except Exception as e:
                self.errors.append(f"File edit error: {e}")
            
            # Small delay between operations
            time.sleep(random.uniform(0.01, 0.05))
    
    def run_db_write_workload(self, duration_sec: int):
        """Write to database concurrently with other agents."""
        end_time = time.time() + duration_sec
        
        while time.time() < end_time:
            try:
                start = time.time()
                
                def db_write():
                    # Simulate DB write
                    db_file = self.work_dir / "test.db"
                    with open(db_file, 'a') as f:
                        f.write(f"Agent {self.agent_id}: {time.time()}\n")
                    return True
                
                result = get_maasl().call_with_stomp_guard(
                    op=db_write,
                    resources=[ResourceDescriptor('CRIT_DB', str(self.work_dir / "test.db"))],
                    intent="db_write",
                    mode="interactive",
                    agent_id=str(self.agent_id),
                    session_id=f"session_{self.agent_id}"
                )
                
                wait_time = time.time() - start
                self.lock_waits.append(wait_time * 1000)
                
                if result:
                    self.operations_completed += 1
                    
            except Exception as e:
                self.errors.append(f"DB write error: {e}")
            
            time.sleep(random.uniform(0.02, 0.1))
    
    def run_mixed_workload(self, duration_sec: int):
        """Run a mix of file edits and DB writes."""
        end_time = time.time() + duration_sec
        
        while time.time() < end_time:
            if random.random() < 0.5:
                # File edit (short duration)
                self.run_file_edit_workload(1)
            else:
                # DB write (short duration)
                self.run_db_write_workload(1)

    def run_docgen_workload(self, duration_sec: int):
        """Simulate concurrent docgen."""
        end_time = time.time() + duration_sec
        
        while time.time() < end_time:
            try:
                start = time.time()
                
                def generate_docs():
                    # Simulate docgen work
                    time.sleep(0.05)
                    return True
                
                result = get_maasl().call_with_stomp_guard(
                    op=generate_docs,
                    resources=[ResourceDescriptor('IDEMP_DOCS', str(self.work_dir))],
                    intent="docgen",
                    mode="batch",  # Docgen is usually batch
                    agent_id=str(self.agent_id),
                    session_id=f"session_{self.agent_id}"
                )
                
                wait_time = time.time() - start
                self.lock_waits.append(wait_time * 1000)
                
                if result:
                    self.operations_completed += 1
                    
            except Exception as e:
                self.errors.append(f"Docgen error: {e}")
            
            time.sleep(random.uniform(0.01, 0.05))

    def run_graph_workload(self, duration_sec: int):
        """Simulate concurrent graph updates."""
        end_time = time.time() + duration_sec
        
        while time.time() < end_time:
            try:
                start = time.time()
                
                def update_graph():
                    # Simulate graph update
                    time.sleep(0.01)
                    return True
                
                result = get_maasl().call_with_stomp_guard(
                    op=update_graph,
                    resources=[ResourceDescriptor('MERGE_META', "main")],
                    intent="graph_update",
                    mode="interactive",
                    agent_id=str(self.agent_id),
                    session_id=f"session_{self.agent_id}"
                )
                
                wait_time = time.time() - start
                self.lock_waits.append(wait_time * 1000)
                
                if result:
                    self.operations_completed += 1
                    
            except Exception as e:
                self.errors.append(f"Graph update error: {e}")
            
            time.sleep(random.uniform(0.01, 0.05))


def run_agent_process(agent_id: int, work_dir: Path, scenario: str, duration: int, result_queue: queue.Queue):
    """Entry point for agent subprocess."""
    agent = AgentSimulator(agent_id, work_dir)
    
    try:
        if scenario == "concurrent_files":
            agent.run_file_edit_workload(duration)
        elif scenario == "concurrent_db":
            agent.run_db_write_workload(duration)
        elif scenario == "mixed":
            agent.run_mixed_workload(duration)
        elif scenario == "concurrent_docs":
            agent.run_docgen_workload(duration)
        elif scenario == "concurrent_graph":
            agent.run_graph_workload(duration)
        
        # Report results
        result_queue.put({
            'agent_id': agent_id,
            'operations': agent.operations_completed,
            'errors': agent.errors,
            'lock_waits': agent.lock_waits,
        })
        
    except Exception as e:
        result_queue.put({
            'agent_id': agent_id,
            'error': str(e),
            'operations': 0,
            'errors': [str(e)],
            'lock_waits': [],
        })


def analyze_results(results: list[dict]):
    """Analyze and report test results."""
    print("\n" + "=" * 70)
    print("MAASL STRESS TEST RESULTS")
    print("=" * 70)
    
    total_ops = sum(r['operations'] for r in results)
    total_errors = sum(len(r['errors']) for r in results)
    all_waits = []
    for r in results:
        all_waits.extend(r['lock_waits'])
    
    print("\n📊 Operations Summary:")
    print(f"  Total operations:     {total_ops}")
    print(f"  Total errors:         {total_errors}")
    print(f"  Success rate:         {(total_ops / (total_ops + total_errors) * 100):.1f}%" 
          if (total_ops + total_errors) > 0 else "N/A")
    
    if all_waits:
        all_waits.sort()
        p50 = all_waits[len(all_waits) // 2]
        p95 = all_waits[int(len(all_waits) * 0.95)]
        p99 = all_waits[int(len(all_waits) * 0.99)]
        
        print("\n⏱️  Lock Wait Times:")
        print(f"  Min:    {min(all_waits):.2f}ms")
        print(f"  P50:    {p50:.2f}ms")
        print(f"  P95:    {p95:.2f}ms")
        print(f"  P99:    {p99:.2f}ms")
        print(f"  Max:    {max(all_waits):.2f}ms")
    
    print("\n🤖 Per-Agent Breakdown:")
    for r in results:
        print(f"  Agent {r['agent_id']}: {r['operations']} ops, "
              f"{len(r['errors'])} errors")
        if r['errors']:
            for err in r['errors'][:3]:  # Show first 3 errors
                print(f"    ⚠️  {err}")
    
    # Success criteria check
    print("\n✅ Success Criteria:")
    success = True
    
    if all_waits:
        if p99 < 500:
            print(f"  ✅ P99 lock wait < 500ms ({p99:.2f}ms)")
        else:
            print(f"  ❌ P99 lock wait >= 500ms ({p99:.2f}ms)")
            success = False
    
    if total_errors == 0:
        print("  ✅ Zero errors")
    else:
        print(f"  ❌ {total_errors} errors occurred")
        success = False
    
    if total_ops > 0:
        print("  ✅ Operations completed successfully")
    else:
        print("  ❌ No operations completed")
        success = False
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 STRESS TEST PASSED!")
    else:
        print("❌ STRESS TEST FAILED - Review errors above")
    print("=" * 70 + "\n")
    
    return success


def main():
    parser = argparse.ArgumentParser(description="MAASL Multi-Agent Stress Test")
    parser.add_argument("--agents", type=int, default=5, 
                        help="Number of concurrent agents (default: 5)")
    parser.add_argument("--duration", type=int, default=30,
                        help="Test duration in seconds (default: 30)")
    parser.add_argument("--scenario", 
                        choices=["concurrent_files", "concurrent_db", "mixed", "concurrent_docs", "concurrent_graph"],
                        default="mixed",
                        help="Test scenario (default: mixed)")
    
    parser.add_argument("--lint", action="store_true",
                        help="Run ruff lint check on generated files")
    
    args = parser.parse_args()
    
    print("\n🚀 Starting MAASL Stress Test")
    print(f"   Agents:   {args.agents}")
    print(f"   Duration: {args.duration}s")
    print(f"   Scenario: {args.scenario}")
    print()
    
    # Create temporary work directory
    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir)
        
        # Start agent threads
        result_queue = queue.Queue()
        threads = []
        
        start_time = time.time()
        
        for i in range(args.agents):
            t = threading.Thread(
                target=run_agent_process,
                args=(i, work_dir, args.scenario, args.duration, result_queue)
            )
            t.start()
            threads.append(t)
        
        # Wait for all agents to complete
        for t in threads:
            t.join()
        
        elapsed = time.time() - start_time
        
        # Collect results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get())
        
        print(f"\n✅ Test completed in {elapsed:.1f}s\n")
        
        # Run lint check if requested
        lint_success = True
        if args.lint:
            print("🔍 Running lint check...")
            import subprocess
            try:
                # Create a dummy pyproject.toml to satisfy ruff if needed, or just run on files
                # We'll just run ruff check on the directory
                # We assume ruff is installed and in path
                cmd = ["ruff", "check", str(work_dir), "--select", "E,F", "--ignore", "F821"] 
                # F821 undefined name 'value' might happen if we just have 'value = ...' without usage? 
                # Actually our file content is valid: "value = 0" is a global assignment.
                
                result = subprocess.run(cmd, check=False, capture_output=True, text=True)
                if result.returncode == 0:
                    print("  ✅ Lint check passed")
                else:
                    print("  ❌ Lint check FAILED")
                    print(result.stdout)
                    print(result.stderr)
                    lint_success = False
            except Exception as e:
                print(f"  ❌ Lint check failed to run: {e}")
                lint_success = False
        
        # Analyze and report
        success = analyze_results(results)
        
        if args.lint and not lint_success:
            success = False
            print("\n❌ LINT CHECK FAILED")
        
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
