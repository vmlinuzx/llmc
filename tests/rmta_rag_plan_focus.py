#!/usr/bin/env python3
"""
RMTA Focus Test - Test rag_plan specifically
"""
import asyncio
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_rag_plan():
    """Test rag_plan specifically."""

    print("=" * 80)
    print("RMTA - Focused rag_plan Testing")
    print("=" * 80)

    # Import MCP client
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as e:
        print(f"ERROR: Failed to import MCP client: {e}")
        return

    # Path to the MCP server
    server_script = Path(__file__).parent.parent / "llmc_mcp" / "server.py"

    if not server_script.exists():
        print(f"ERROR: Server script not found at {server_script}")
        return

    print(f"Target Server: {server_script}")

    # Start the MCP client
    server_params = StdioServerParameters(
        command="python",
        args=[str(server_script)],
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            client = ClientSession(read, write)
            await client.initialize()
            
            # Check if rag_plan is available
            tools_result = await client.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            
            if "rag_plan" not in tool_names:
                print("❌ FAILURE: rag_plan tool not found in registered tools!")
                print(f"Available tools: {tool_names}")
                return

            print("✓ rag_plan found in tools")
            
            # Execute the test
            print("\nExecuting: rag_plan(query='how to use tools')")
            
            try:
                result = await client.call_tool("rag_plan", {"query": "how to use tools"})
                
                if not result:
                    print("⚠️ WARNING: Empty result returned")
                else:
                    print("\nResponse Content:")
                    for content in result.content:
                        print(f"Type: {content.type}")
                        print(f"Text: {content.text}")
                        
                        # specific check for error strings often wrapped in text
                        if "error" in content.text.lower() and "traceback" in content.text.lower():
                             print("\n❌ FAILURE: Tool returned an error trace.")
                        elif "error" in content.text.lower():
                             print("\n⚠️ WARNING: Tool returned an error message.")
                             
            except Exception as e:
                print(f"\n❌ EXCEPTION during tool call: {e}")

    except Exception as e:
        print(f"\n❌ SETUP EXCEPTION: {e}")

if __name__ == "__main__":
    asyncio.run(test_rag_plan())
