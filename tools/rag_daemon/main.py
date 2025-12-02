"""Main entrypoint wiring for LLMC RAG Daemon."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import os
from pathlib import Path
import sys

from .config import load_config
from .logging_utils import get_logger
from .models import DaemonConfig
from .registry import RegistryClient
from .scheduler import Scheduler
from .state_store import StateStore
from .workers import WorkerPool


def _print_top_level_help() -> None:
    """Print a tree-style help overview for llmc-rag-daemon."""
    print(
        
            "LLMC RAG Daemon\n\n"
            "Run the scheduler + workers that keep RAG workspaces fresh.\n\n"
            "Usage:\n"
            "  llmc-rag-daemon [command] [options]\n\n"
            "Commands:\n"
            "  run         Run the daemon until interrupted (default)\n"
            "  tick        Run a single scheduler tick and exit\n"
            "  config      Show the effective configuration\n"
            "  doctor      Run basic health checks (paths, registry, state store)\n\n"
            "Global options:\n"
            "  --config PATH      Path to rag-daemon.yml "
            "(default: $LLMC_RAG_DAEMON_CONFIG or ~/.llmc/rag-daemon.yml)\n"
            "  --log-level LEVEL  DEBUG, INFO, WARNING, ERROR (default from config)\n\n"
            "Examples:\n"
            "  llmc-rag-daemon\n"
            "  llmc-rag-daemon run --config ~/.llmc/rag-daemon.yml\n"
            "  llmc-rag-daemon tick\n"
            "  llmc-rag-daemon config --json\n"
        
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llmc-rag-daemon",
        description="LLMC RAG Daemon - scheduler and worker loop for RAG refresh",
    )
    parser.add_argument(
        "--config",
        default=None,
        help=(
            "Path to daemon config file "
            "(defaults to LLMC_RAG_DAEMON_CONFIG or ~/.llmc/rag-daemon.yml)"
        ),
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Override log level (DEBUG, INFO, WARNING, ERROR)",
    )
    sub = parser.add_subparsers(dest="command")
    sub.required = False  # default to 'run' when omitted

    sub.add_parser("run", help="Run the daemon until interrupted")

    sub.add_parser("tick", help="Run a single scheduler tick and exit")

    p_config = sub.add_parser("config", help="Show effective configuration")
    p_config.add_argument("--json", action="store_true", help="JSON output")

    sub.add_parser("doctor", help="Run basic health checks")

    return parser


def _make_scheduler(config: DaemonConfig) -> tuple[Scheduler, any]:
    logger = get_logger("rag_daemon.main", config)
    registry = RegistryClient.from_config(config)
    state_store = StateStore(config.state_store_path)
    workers = WorkerPool(config=config, state_store=state_store)
    scheduler = Scheduler(
        config=config,
        registry=registry,
        state_store=state_store,
        workers=workers,
    )
    return scheduler, logger


def _cmd_run(config: DaemonConfig) -> int:
    scheduler, logger = _make_scheduler(config)
    logger.info("LLMC RAG Daemon starting up (run)")
    try:
        scheduler.run_forever()
    except KeyboardInterrupt:  # pragma: no cover - interactive
        logger.info("LLMC RAG Daemon interrupted by user, shutting down")
    logger.info("LLMC RAG Daemon shut down")
    return 0


def _cmd_tick(config: DaemonConfig) -> int:
    scheduler, logger = _make_scheduler(config)
    logger.info("Running single LLMC RAG Daemon tick")
    scheduler.run_once()
    logger.info("Single LLMC RAG Daemon tick complete")
    return 0


def _cmd_config(config: DaemonConfig, json_output: bool) -> int:
    from json import dumps

    data = asdict(config)
    for key, value in list(data.items()):
        if isinstance(value, Path):
            data[key] = str(value)

    if json_output:
        print(dumps(data, indent=2))
    else:
        print("LLMC RAG Daemon effective configuration")
        for key in sorted(data.keys()):
            print(f"{key}: {data[key]}")
    return 0


def _cmd_doctor(config: DaemonConfig) -> int:
    """Basic health checks for daemon environment."""
    ok = True

    print("LLMC RAG Daemon Doctor")
    print("======================")

    # Registry file
    registry_path = config.registry_path
    if not registry_path.exists():
        print(f"[WARN] Registry file does not exist: {registry_path}")
        print("       Daemon will idle with 0 repos until one is registered.")
    else:
        if not os.access(registry_path, os.R_OK):
            print(f"[ERROR] Registry not readable: {registry_path}")
            ok = False

    # State store / log / control directories (existence + basic writability)
    for label, path in [
        ("state_store_path", config.state_store_path),
        ("log_path", config.log_path),
        ("control_dir", config.control_dir),
    ]:
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"[INFO] Created missing {label} directory at {path}")
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[ERROR] Could not create {label} directory {path}: {exc}")
                ok = False
                continue

        if not os.access(path, os.W_OK):
            print(f"[ERROR] {label} not writable: {path}")
            ok = False
        else:
            print(f"[OK] {label}: {path}")

    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help"):
        _print_top_level_help()
        return 0

    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse already printed a helpful message
        return int(exc.code)

    try:
        config = load_config(args.config)
    except FileNotFoundError as exc:
        print(f"error: {exc}")
        print(
            "Hint: create a daemon config at ~/.llmc/rag-daemon.yml "
            "or set LLMC_RAG_DAEMON_CONFIG / pass --config."
        )
        return 1
    except Exception as exc:  # pragma: no cover - defensive
        print(f"error: failed to load daemon config: {exc}")
        return 1

    if getattr(args, "log_level", None):
        config = replace(config, log_level=str(args.log_level))

    command = args.command or "run"

    if command == "run":
        return _cmd_run(config)
    if command == "tick":
        return _cmd_tick(config)
    if command == "config":
        return _cmd_config(config, json_output=getattr(args, "json", False))
    if command == "doctor":
        return _cmd_doctor(config)

    print(f"error: unknown command '{command}'")
    _print_top_level_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
