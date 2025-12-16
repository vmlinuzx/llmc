#!/usr/bin/env python3
import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.getcwd())

try:
    from llmc_mcp.server import TOOLS
except ImportError as e:
    print(f"Error importing tools: {e}")
    sys.exit(1)

OUTPUT_FILE = "DOCS/reference/mcp-tools/index.md"

def main():
    md_lines = []
    md_lines.append("# MCP Tool Reference")
    md_lines.append("\nReference documentation for all available MCP tools.\n")
    
    # Sort tools by name
    tools = sorted(TOOLS, key=lambda x: x.name)
    
    for tool in tools:
        md_lines.append(f"## `{tool.name}`")
        md_lines.append(f"{tool.description}\n")
        
        md_lines.append("### Arguments")
        schema = tool.inputSchema
        props = schema.get("properties", {})
        required = schema.get("required", [])
        
        if not props:
            md_lines.append("_No arguments._")
        else:
            md_lines.append("| Name | Type | Required | Description |")
            md_lines.append("|---|---|---|---|")
            
            for prop_name, prop_data in props.items():
                prop_type = prop_data.get("type", "any")
                is_req = "Yes" if prop_name in required else "No"
                desc = prop_data.get("description", "-")
                
                # Check for enums
                if "enum" in prop_data:
                    desc += f" Allowed: `{prop_data['enum']}`"
                    
                # Check for defaults
                if "default" in prop_data:
                    desc += f" (Default: `{prop_data['default']}`)"
                
                md_lines.append(f"| `{prop_name}` | `{prop_type}` | {is_req} | {desc} |")
        
        md_lines.append("\n---\n")

    output_dir = os.path.dirname(OUTPUT_FILE)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(OUTPUT_FILE, "w") as f:
        f.write("\n".join(md_lines))
        
    print(f"Wrote {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
