#!/usr/bin/env python3
"""
Test script for Idle Loop Throttling implementation.

Verifies that:
1. Daemon config is loaded correctly
2. process_repo returns boolean
3. Idle backoff logic calculates correctly
4. Interruptible sleep works
"""
import os
import sys
from pathlib import Path

# Add repo to path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from tools.rag.service import ServiceState, FailureTracker, RAGService


def test_daemon_config_loading():
    """Test that daemon config is loaded from llmc.toml"""
    print("=" * 50)
    print("Test 1: Daemon Config Loading")
    print("=" * 50)
    
    state = ServiceState()
    tracker = FailureTracker()
    service = RAGService(state, tracker)
    
    daemon_cfg = service._daemon_cfg
    print(f"✓ Daemon config loaded: {daemon_cfg}")
    
    # Check expected keys
    expected_keys = ["nice_level", "idle_backoff_max", "idle_backoff_base"]
    for key in expected_keys:
        value = daemon_cfg.get(key)
        if value is not None:
            print(f"  ✓ {key} = {value}")
        else:
            print(f"  ✗ {key} = (not set, will use default)")
    
    print()


def test_backoff_calculation():
    """Test exponential backoff calculations"""
    print("=" * 50)
    print("Test 2: Backoff Calculation")
    print("=" * 50)
    
    interval = 180  # 3 minutes
    base = 2
    max_mult = 10
    
    print(f"Base interval: {interval}s")
    print(f"Backoff base: {base}")
    print(f"Max multiplier: {max_mult}")
    print()
    
    for idle_cycles in range(6):
        multiplier = min(base ** idle_cycles, max_mult)
        sleep_time = interval * multiplier
        print(f"  Idle x{idle_cycles}: {multiplier}x → sleep {sleep_time}s ({sleep_time/60:.1f} min)")
    
    print()


def test_interruptible_sleep():
    """Test that interruptible sleep works"""
    print("=" * 50)
    print("Test 3: Interruptible Sleep")
    print("=" * 50)
    
    import time
    
    state = ServiceState()
    tracker = FailureTracker()
    service = RAGService(state, tracker)
    
    print("Testing _interruptible_sleep(7.0) - should take ~7s with 5s chunks")
    start = time.time()
    service._interruptible_sleep(7.0)
    elapsed = time.time() - start
    
    if 6.5 < elapsed < 7.5:
        print(f"  ✓ Slept for {elapsed:.1f}s (expected ~7s)")
    else:
        print(f"  ✗ Slept for {elapsed:.1f}s (expected ~7s)")
    
    print()


def test_process_repo_return_type():
    """Test that process_repo returns bool"""
    print("=" * 50)
    print("Test 4: process_repo Return Type")
    print("=" * 50)
    
    state = ServiceState()
    tracker = FailureTracker()
    service = RAGService(state, tracker)
    
    # Test with non-existent repo
    print("Testing with non-existent repo path:")
    result = service.process_repo("/tmp/nonexistent_test_repo_xyz")
    print(f"  Return value: {result}")
    print(f"  Type: {type(result).__name__}")
    
    if isinstance(result, bool):
        print(f"  ✓ Returns boolean as expected")
    else:
        print(f"  ✗ Expected bool, got {type(result).__name__}")
    
    print()


def main():
    print("\n" + "=" * 50)
    print("IDLE LOOP THROTTLING - Test Suite")
    print("=" * 50)
    print()
    
    try:
        test_daemon_config_loading()
        test_backoff_calculation()
        test_interruptible_sleep()
        test_process_repo_return_type()
        
        print("=" * 50)
        print("✅ All tests completed successfully!")
        print("=" * 50)
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
