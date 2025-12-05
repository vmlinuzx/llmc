#!/usr/bin/env python3
"""
Quick validation test for RAG navigation tools fix.
Tests that the tools work when called via code execution mode.
"""

from pathlib import Path
import sys

# Add llmc to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llmc_mcp.config import load_config
from llmc_mcp.server import LlmcMcpServer


async def test_rag_nav_tools():
    """Test that RAG navigation tools work in code_exec mode."""
    print("=" * 60)
    print("Testing RAG Navigation Tools in Code Execution Mode")
    print("=" * 60)
    
    # Load config
    config = load_config()
    
    # Create server instance
    server = LlmcMcpServer(config)
    
    # Check if we're in code_exec mode
    if not config.code_execution.enabled:
        print("⚠️  Code execution mode not enabled in config")
        print("   Skipping test (tools working in classic mode)")
        return
    
    print("\n✓ Server initialized in code_exec mode")
    print(f"  Registered tools: {len(server.tools)}")
    
    # Test tools via execute_code (simulating stub calls)
    test_cases = [
        {
            "name": "rag_where_used",
            "code": """
from stubs import rag_where_used
try:
    result = rag_where_used(symbol="EnrichmentPipeline", limit=5)
    print(f"SUCCESS: rag_where_used returned {type(result)}")
except Exception as e:
    print(f"ERROR: {e}")
"""
        },
        {
            "name": "rag_lineage",
            "code": """
from stubs import rag_lineage  
try:
    result = rag_lineage(symbol="EnrichmentPipeline", direction="downstream", limit=5)
    print(f"SUCCESS: rag_lineage returned {type(result)}")
except Exception as e:
    print(f"ERROR: {e}")
"""
        },
        {
            "name": "inspect",
            "code": """
from stubs import inspect
try:
    result = inspect(path="tools/rag/enrichment_pipeline.py")
    print(f"SUCCESS: inspect returned {type(result)}")
except Exception as e:
    print(f"ERROR: {e}")
"""
        },
        {
            "name": "rag_stats",
            "code": """
from stubs import rag_stats
try:
    result = rag_stats()
    print(f"SUCCESS: rag_stats returned {type(result)}")
except Exception as e:
    print(f"ERROR: {e}")
"""
        },
        {
            "name": "rag_plan",
            "code": """
from stubs import rag_plan
try:
    result = rag_plan(query="routing logic")
    print(f"SUCCESS: rag_plan returned {type(result)}")
except Exception as e:
    print(f"ERROR: {e}")
"""
        },
    ]
    
    print("\n" + "=" * 60)
    print("Testing Tools")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\n Testing: {test['name']}")
        print("-" * 60)
        
        try:
            # Call execute_code handler
            result = await server._handle_execute_code({"code": test["code"]})
            
            if result and len(result) > 0:
                response = result[0].text
                
                # Check for success or error
                if "SUCCESS:" in response:
                    print(f"✅ {test['name']}: PASSED")
                    passed += 1
                elif "ERROR:" in response or "error" in response.lower():
                    print(f"❌ {test['name']}: FAILED")
                    print(f"   Response: {response[:200]}")
                    failed += 1
                else:
                    print(f"⚠️  {test['name']}: UNKNOWN")
                    print(f"   Response: {response[:200]}")
            else:
                print(f"❌ {test['name']}: No response")
                failed += 1
                
        except Exception as e:
            print(f"❌ {test['name']}: EXCEPTION - {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return passed, failed


if __name__ == "__main__":
    import asyncio
    passed, failed = asyncio.run(test_rag_nav_tools())
    sys.exit(0 if failed == 0 else 1)
