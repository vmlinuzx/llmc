#!/usr/bin/env python3
"""Generate CLI reference documentation from --help output."""
from datetime import datetime
import os
import subprocess

# CLI entry points from pyproject.toml [project.scripts]
CLI_COMMANDS = [
    ("llmc-cli", "llmc.main", "Primary CLI for LLMC operations"),
    ("llmc-mcp", "llmc_mcp.cli", "MCP server for Claude Desktop integration"),
    ("te", "llmc.te.cli", "Tool Envelope - intelligent command wrapper"),
    ("llmc-chat", "llmc_agent.cli", "Chat agent CLI (also: bx)"),
    ("mcgrep", "llmc.mcgrep", "Semantic grep with RAG context"),
]

OUTPUT_DIR = "DOCS/reference/cli"


def run_help(command_name):
    """Run command --help and capture output."""
    try:
        result = subprocess.run(
            [command_name, "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout
        return f"Command exited with code {result.returncode}\n{result.stderr}"
    except FileNotFoundError:
        return f"Command '{command_name}' not found in PATH"
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as e:
        return f"Error: {e}"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    index_lines = [
        "# CLI Reference",
        "",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "## Available Commands",
        "",
        "| Command | Description |",
        "|---------|-------------|",
    ]

    for cmd_name, module, description in CLI_COMMANDS:
        index_lines.append(f"| [`{cmd_name}`]({cmd_name}.md) | {description} |")

    index_lines.extend(["", "---", ""])

    for cmd_name, module, description in CLI_COMMANDS:
        print(f"Generating docs for {cmd_name}...")
        help_text = run_help(cmd_name)

        filename = f"{cmd_name}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        with open(filepath, "w") as f:
            f.write(f"# {cmd_name}\n\n")
            f.write(f"{description}\n\n")
            f.write(f"**Module:** `{module}`\n\n")
            f.write("## Usage\n\n")
            f.write("```text\n")
            f.write(help_text)
            f.write("```\n")

        print(f"  Wrote {filepath}")

    # Write index
    index_path = os.path.join(OUTPUT_DIR, "index.md")
    with open(index_path, "w") as f:
        f.write("\n".join(index_lines))
    print(f"Wrote {index_path}")


if __name__ == "__main__":
    main()
