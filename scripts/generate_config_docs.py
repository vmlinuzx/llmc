#!/usr/bin/env python3
"""Generate config reference documentation from llmc.toml."""
from datetime import datetime
import os
import sys

try:
    import tomli
except ImportError:
    import tomllib as tomli

SOURCE_TOML = "llmc.toml"  # Repo root, not llmc/llmc.toml
OUTPUT_FILE = "DOCS/reference/config/llmc-toml.md"


def format_value(value):
    """Format a value for display."""
    if isinstance(value, str):
        if len(value) > 60:
            return f'"{value[:57]}..."'
        return f'"{value}"'
    elif isinstance(value, list):
        if len(value) > 3:
            return f"[{', '.join(map(str, value[:3]))}... ({len(value)} items)]"
        return str(value)
    elif isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def extract_sections(config, prefix=""):
    """Recursively extract config sections."""
    sections = []

    for key, value in config.items():
        full_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            # Check if it's a table or has nested values
            has_nested_dicts = any(isinstance(v, dict) for v in value.values())
            if has_nested_dicts:
                sections.extend(extract_sections(value, full_key))
            else:
                # It's a leaf table - document its keys
                sections.append((full_key, value))
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # Array of tables
            sections.append((f"[[{full_key}]]", value[0]))
        # Skip scalar values at top level

    return sections


def main():
    if not os.path.exists(SOURCE_TOML):
        print(f"Error: {SOURCE_TOML} not found. Run from repo root.")
        sys.exit(1)

    with open(SOURCE_TOML, "rb") as f:
        config = tomli.load(f)

    lines = [
        "# llmc.toml Reference",
        "",
        f"_Generated from `{SOURCE_TOML}` on {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "This is an auto-generated reference of all configuration keys.",
        "For a human-friendly guide, see [Configuration Guide](../../user-guide/configuration.md).",
        "",
        "---",
        "",
    ]

    # Document top-level sections
    for section_name in sorted(config.keys()):
        section = config[section_name]
        lines.append(f"## [{section_name}]")
        lines.append("")

        if isinstance(section, dict):
            # Find scalar values in this section
            scalars = {
                k: v for k, v in section.items() if not isinstance(v, (dict, list))
            }
            if scalars:
                lines.append("| Key | Type | Value |")
                lines.append("|-----|------|-------|")
                for k, v in scalars.items():
                    lines.append(
                        f"| `{k}` | `{type(v).__name__}` | `{format_value(v)}` |"
                    )
                lines.append("")

            # Find nested tables
            for k, v in section.items():
                if isinstance(v, dict):
                    lines.append(f"### [{section_name}.{k}]")
                    lines.append("")
                    lines.append("| Key | Type | Value |")
                    lines.append("|-----|------|-------|")
                    for sk, sv in v.items():
                        if not isinstance(sv, dict):
                            lines.append(
                                f"| `{sk}` | `{type(sv).__name__}` | `{format_value(sv)}` |"
                            )
                    lines.append("")
        elif isinstance(section, list):
            lines.append(f"_Array of {len(section)} entries_")
            lines.append("")
        else:
            lines.append(f"Value: `{format_value(section)}`")
            lines.append("")

    # Write output
    output_dir = os.path.dirname(OUTPUT_FILE)
    os.makedirs(output_dir, exist_ok=True)

    with open(OUTPUT_FILE, "w") as f:
        f.write("\n".join(lines))

    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
