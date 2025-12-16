#!/usr/bin/env python3
import sys
import tomli
import os

SOURCE_TOML = "llmc/llmc.toml"
OUTPUT_FILE = "DOCS/reference/config/llmc-toml.md"

def generate_table(data, prefix=""):
    lines = []
    lines.append("| Key | Type | Example | Description |")
    lines.append("|---|---|---|---|")
    
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        
        if isinstance(value, dict):
            # Recursively generate for sections
            # But first print the section header if we want?
            # Actually, let's just flatten the keys or link to sections.
            # For simplicity, let's just document the nested keys.
            lines.extend(generate_table(value, full_key)[2:]) # Skip header of recursive call
        else:
            val_type = type(value).__name__
            val_str = str(value)
            if len(val_str) > 50:
                val_str = val_str[:47] + "..."
            lines.append(f"| `{full_key}` | {val_type} | `{val_str}` | - |")
            
    return lines

def main():
    if not os.path.exists(SOURCE_TOML):
        print(f"Error: {SOURCE_TOML} not found.")
        sys.exit(1)
        
    with open(SOURCE_TOML, "rb") as f:
        config = tomli.load(f)
        
    md_lines = []
    md_lines.append("# llmc.toml Configuration Reference")
    md_lines.append("\nGenerated from `llmc/llmc.toml` default values.\n")
    
    # Iterate top-level sections
    for section, content in config.items():
        md_lines.append(f"## [{section}]")
        if isinstance(content, dict):
            md_lines.extend(generate_table(content))
        else:
             md_lines.append(f"Global key: `{section}` = {content}")
        md_lines.append("\n")

    output_dir = os.path.dirname(OUTPUT_FILE)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(OUTPUT_FILE, "w") as f:
        f.write("\n".join(md_lines))
        
    print(f"Wrote {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
