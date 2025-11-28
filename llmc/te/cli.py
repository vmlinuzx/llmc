#!/usr/bin/env python3
"""
Tool Envelope CLI.

Shell-level middleware that intercepts standard commands and returns
enriched, ranked, progressively-disclosed output.

Usage:
    te <command> [args...]       # run command (enriched if known, pass-through if not)
    te -i <command> [args...]    # force raw/pass-through (no enrichment)
    te --handle res_01H...       # retrieve stored result
    te --list-handles            # list available handles
    
Known enriched commands: grep, cat, find
Unknown commands are passed through to bash with telemetry logging.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from .config import _find_repo_root, get_te_config
from .handlers import handle_grep
from .store import get_entry, list_handles, load
from .telemetry import TeTimer, log_event


# Commands that have enriched handlers
ENRICHED_COMMANDS = {"grep", "cat", "find"}


def _parse_args() -> tuple[argparse.Namespace, list[str]]:
    """
    Parse command line arguments.
    
    Returns (parsed_args, remaining_args) to allow pass-through of unknown flags.
    """
    parser = argparse.ArgumentParser(
        prog="te",
        description="Tool Envelope - enriched shell commands for LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  te grep "pattern" path/          # enriched grep with ranking
  te -i grep "pattern"             # raw grep (no enrichment)
  te ls -la                        # pass-through to bash
  te --list-handles                # show stored results
  
Known enriched commands: grep, cat, find
All other commands pass through to bash with telemetry.
        """,
    )

    parser.add_argument(
        "-i", "--raw",
        action="store_true",
        help="Force raw/pass-through mode (skip enrichment even for known commands)",
    )

    parser.add_argument(
        "--handle",
        metavar="ID",
        help="Retrieve stored result by handle ID",
    )

    parser.add_argument(
        "--chunk",
        type=int,
        default=0,
        metavar="N",
        help="Chunk number for paginated handle retrieval (default: 0)",
    )

    parser.add_argument(
        "--list-handles",
        action="store_true",
        help="List all stored result handles",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show telemetry statistics",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Show TE version",
    )

    # Use parse_known_args to allow pass-through of command args
    return parser.parse_known_args()


def _handle_retrieve(handle: str, chunk: int = 0) -> int:
    """Retrieve stored result by handle."""
    data = load(handle)
    if data is None:
        print(f"[TE] handle not found: {handle}", file=sys.stderr)
        return 1

    entry = get_entry(handle)

    # For now, just dump the data. Future: chunk-based pagination
    if isinstance(data, str):
        print(data)
    else:
        print(str(data))

    return 0


def _handle_list_handles() -> int:
    """List all stored handles."""
    handles = list_handles()
    if not handles:
        print("[TE] no stored handles")
        return 0

    for h in handles:
        entry = get_entry(h)
        if entry:
            age_s = int(__import__("time").time() - entry.created)
            print(f"{h}  cmd={entry.cmd}  size={entry.total_size}  age={age_s}s")
        else:
            print(h)
    return 0


def _handle_stats(repo_root: Path) -> int:
    """Show telemetry statistics from SQLite database."""
    import sqlite3
    
    db_path = repo_root / ".llmc" / "te_telemetry.db"
    if not db_path.exists():
        print("[TE] no telemetry data yet")
        return 0
    
    conn = sqlite3.connect(db_path)
    try:
        # Overall stats
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as total_calls,
                COUNT(DISTINCT cmd) as unique_cmds,
                AVG(latency_ms) as avg_latency,
                SUM(output_size) as total_output_bytes
            FROM telemetry_events
        """)
        total_calls, unique_cmds, avg_latency, total_output = cursor.fetchone()
        
        print(f"[TE] Telemetry Summary")
        print(f"  Total calls: {total_calls}")
        print(f"  Unique commands: {unique_cmds}")
        print(f"  Avg latency: {avg_latency:.1f}ms")
        print(f"  Total output: {total_output / 1024:.1f} KB")
        print()
        
        # By command and mode
        print("[TE] Command Usage:")
        cursor = conn.execute("""
            SELECT 
                cmd,
                mode,
                COUNT(*) as count,
                AVG(latency_ms) as avg_latency,
                SUM(output_size) as total_bytes
            FROM telemetry_events 
            GROUP BY cmd, mode 
            ORDER BY count DESC
            LIMIT 20
        """)
        
        for cmd, mode, count, avg_lat, total_bytes in cursor.fetchall():
            print(f"  {cmd:15} {mode:12} {count:4}x  {avg_lat:5.1f}ms  {total_bytes/1024:7.1f}KB")
        
        # Recent activity
        print()
        print("[TE] Recent Activity (last 10):")
        cursor = conn.execute("""
            SELECT timestamp, cmd, mode, latency_ms
            FROM telemetry_events 
            ORDER BY id DESC 
            LIMIT 10
        """)
        
        for ts, cmd, mode, lat in cursor.fetchall():
            # Strip timezone for readability
            ts_short = ts.replace("T", " ").split(".")[0]
            print(f"  {ts_short}  {cmd:12} {mode:12} {lat:4}ms")
        
    finally:
        conn.close()
    
    return 0


def _handle_grep(args: list[str], raw: bool, repo_root: Path) -> int:
    """Handle grep subcommand."""
    if not args:
        print("[TE] grep requires a pattern", file=sys.stderr)
        return 1

    pattern = args[0]
    path = args[1] if len(args) > 1 else None
    agent_id = os.getenv("TE_AGENT_ID")

    with TeTimer() as timer:
        result = handle_grep(
            pattern=pattern,
            path=path,
            raw=raw,
            agent_id=agent_id,
            repo_root=repo_root,
        )

    # Output
    output = result.render()
    print(output)

    # Telemetry
    meta = result.header
    truncated = '"truncated":true' in meta or '"truncated": true' in meta
    handle_created = '"handle":' in meta

    log_event(
        cmd="grep",
        mode="raw" if raw else "enriched",
        input_size=len(result.content),
        output_size=len(output),
        truncated=truncated,
        handle_created=handle_created,
        latency_ms=timer.elapsed_ms,
        repo_root=repo_root,
    )

    return 0


def _handle_passthrough(command: str, args: list[str], repo_root: Path) -> int:
    """
    Pass-through handler for unknown commands.
    
    Executes command via bash subprocess and logs telemetry.
    This is the whole point of TE - transparent wrapper that logs everything.
    """
    # Build full command
    cmd_parts = [command] + args
    full_cmd = " ".join(cmd_parts)
    
    with TeTimer() as timer:
        try:
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,  # TODO: make configurable
            )
            
            # Output stdout/stderr as-is
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)
            
            output_size = len(result.stdout) + len(result.stderr)
            exit_code = result.returncode
            error = None
            
        except subprocess.TimeoutExpired:
            print(f"[TE] command timed out after 30s: {full_cmd}", file=sys.stderr)
            output_size = 0
            exit_code = 124  # timeout exit code
            error = "timeout"
            
        except Exception as e:
            print(f"[TE] execution failed: {e}", file=sys.stderr)
            output_size = 0
            exit_code = 1
            error = str(e)
    
    # Log telemetry for pass-through command
    log_event(
        cmd=command,
        mode="passthrough",
        input_size=len(full_cmd),
        output_size=output_size,
        truncated=False,
        handle_created=False,
        latency_ms=timer.elapsed_ms,
        repo_root=repo_root,
        error=error,
    )
    
    return exit_code


def main() -> int:
    """Main entry point."""
    args, remaining = _parse_args()

    # Version
    if args.version:
        from . import __version__
        print(f"te {__version__}")
        return 0

    # List handles
    if args.list_handles:
        return _handle_list_handles()
    
    # Show stats
    if args.stats:
        repo_root = _find_repo_root()
        return _handle_stats(repo_root)

    # Retrieve handle
    if args.handle:
        return _handle_retrieve(args.handle, args.chunk)

    # Parse command and args from remaining
    if not remaining:
        print("[TE] usage: te [-i] <command> [args...]", file=sys.stderr)
        print("[TE] enriched commands: grep, cat, find", file=sys.stderr)
        print("[TE] other commands pass through to bash", file=sys.stderr)
        print("[TE] try: te --help", file=sys.stderr)
        return 1
    
    command = remaining[0]
    cmd_args = remaining[1:] if len(remaining) > 1 else []

    # Find repo root
    repo_root = _find_repo_root()
    cfg = get_te_config(repo_root)

    if not cfg.enabled:
        print("[TE] disabled in config", file=sys.stderr)
        return 1

    # Check if this is a known enriched command
    is_enriched = command in ENRICHED_COMMANDS
    
    # If -i/--raw is set, OR command is unknown, do pass-through
    if args.raw or not is_enriched:
        return _handle_passthrough(command, cmd_args, repo_root)
    
    # Dispatch to enriched handler
    if command == "grep":
        return _handle_grep(cmd_args, raw=False, repo_root=repo_root)

    elif command == "cat":
        # Phase 1 - not yet implemented, fall back to pass-through
        print("[TE] cat enrichment not yet implemented, using pass-through", file=sys.stderr)
        return _handle_passthrough(command, cmd_args, repo_root)

    elif command == "find":
        # Phase 1 - not yet implemented, fall back to pass-through
        print("[TE] find enrichment not yet implemented, using pass-through", file=sys.stderr)
        return _handle_passthrough(command, cmd_args, repo_root)

    # Should never reach here
    return 1


if __name__ == "__main__":
    sys.exit(main())
