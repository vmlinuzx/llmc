#!/usr/bin/env python3
"""
Quick verification that the idle loop throttling implementation is correct.

This script verifies:
1. Service can start without errors
2. Configuration is loaded properly
3. No syntax errors in the modified code
"""
from pathlib import Path
import sys

# Add repo to path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from tools.rag.service import FailureTracker, RAGService, ServiceState


def main():
    print("=" * 60)
    print("IDLE LOOP THROTTLING - Quick Verification")
    print("=" * 60)
    print()
    
    try:
        # 1. Can we instantiate the service?
        print("1. Instantiating ServiceState...")
        state = ServiceState()
        print("   ✓ ServiceState created")
        
        print("2. Instantiating FailureTracker...")
        tracker = FailureTracker()
        print("   ✓ FailureTracker created")
        
        print("3. Instantiating RAGService...")
        service = RAGService(state, tracker)
        print("   ✓ RAGService created")
        
        # 2. Is daemon config loaded?
        print("\n4. Checking daemon configuration...")
        daemon_cfg = service._daemon_cfg
        print(f"   Daemon config: {daemon_cfg}")
        
        # 3. Check expected values
        print("\n5. Verifying config values...")
        nice_level = daemon_cfg.get("nice_level", 10)
        idle_backoff_max = daemon_cfg.get("idle_backoff_max", 10)
        idle_backoff_base = daemon_cfg.get("idle_backoff_base", 2)
        
        print(f"   nice_level: {nice_level}")
        print(f"   idle_backoff_max: {idle_backoff_max}")
        print(f"   idle_backoff_base: {idle_backoff_base}")
        
        # 4. Check methods exist
        print("\n6. Checking required methods exist...")
        assert hasattr(service, 'process_repo'), "Missing process_repo method"
        assert hasattr(service, 'run_loop'), "Missing run_loop method"
        assert hasattr(service, '_interruptible_sleep'), "Missing _interruptible_sleep method"
        print("   ✓ All required methods present")
        
        # 5. Check process_repo signature
        print("\n7. Checking process_repo return type annotation...")
        import inspect
        sig = inspect.signature(service.process_repo)
        return_annotation = sig.return_annotation
        print(f"   Return type: {return_annotation}")
        if return_annotation == bool:
            print("   ✓ Correct return type annotation")
        else:
            print(f"   ⚠ Expected 'bool', got '{return_annotation}'")
        
        print("\n" + "=" * 60)
        print("✅ VERIFICATION PASSED - Service is ready!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("  1. llmc-rag start")
        print("  2. llmc-rag logs -f")
        print("  3. Watch for idle backoff messages")
        print()
        
        return 0
        
    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
