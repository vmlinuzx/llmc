#!/usr/bin/env python3
"""Generate MCP tool reference documentation from tool definitions."""
from datetime import datetime
import os
import sys

# Add project root to path
sys.path.insert(0, os.getcwd())

OUTPUT_FILE = "DOCS/reference/mcp-tools/index.md"


def main():
    try:
        from llmc_mcp.server import TOOLS
    except ImportError as e:
        print(f"Error importing TOOLS from llmc_mcp.server: {e}")
        print("Make sure llmc is installed: pip install -e '.[rag]'")
        sys.exit(1)

    lines = [
        "# MCP Tool Reference",
        "",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        f"LLMC exposes **{len(TOOLS)} tools** via the Model Context Protocol.",
        "",
        "## Tool Categories",
        "",
        "| Category | Tools |",
        "|----------|-------|",
    ]

    # Categorize tools by prefix
    categories = {}
    for tool in TOOLS:
        prefix = tool.name.split("_")[0] if "_" in tool.name else "other"
        categories.setdefault(prefix, []).append(tool)

    for cat, tools in sorted(categories.items()):
        tool_names = ", ".join(f"`{t.name}`" for t in tools)
        lines.append(f"| {cat} | {tool_names} |")

    lines.extend(["", "---", ""])

    # Document each tool
    for tool in sorted(TOOLS, key=lambda x: x.name):
        lines.append(f"## `{tool.name}`")
        lines.append("")
        lines.append(tool.description)
        lines.append("")

        schema = tool.inputSchema
        props = schema.get("properties", {})
        required = set(schema.get("required", []))

        if props:
            lines.append("### Parameters")
            lines.append("")
            lines.append("| Name | Type | Required | Description |")
            lines.append("|------|------|----------|-------------|")

            for prop_name, prop_data in props.items():
                prop_type = prop_data.get("type", "any")
                is_req = "✓" if prop_name in required else ""
                desc = prop_data.get("description", "-")

                # Add enum info
                if "enum" in prop_data:
                    desc += f" Values: `{prop_data['enum']}`"

                # Add default
                if "default" in prop_data:
                    desc += f" (default: `{prop_data['default']}`)"

                lines.append(f"| `{prop_name}` | `{prop_type}` | {is_req} | {desc} |")
            lines.append("")
        else:
            lines.append("_No parameters_")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Write output
    output_dir = os.path.dirname(OUTPUT_FILE)
    os.makedirs(output_dir, exist_ok=True)

    with open(OUTPUT_FILE, "w") as f:
        f.write("\n".join(lines))

    print(f"Wrote {OUTPUT_FILE} ({len(TOOLS)} tools documented)")


if __name__ == "__main__":
    main()
