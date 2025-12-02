from pathlib import Path

import tomli_w
import typer

from llmc.core import find_repo_root

try:
    import tomllib
except ImportError:
    import tomli as tomllib

# Import Database to initialize schema
from tools.rag.database import Database

app = typer.Typer()

DEFAULT_CONFIG = {
    "storage": {"index_path": ".llmc/index_v2.db"},
    "logging": {
        "log_directory": ".llmc/logs",
        "enable_rotation": True,
        "max_file_size_mb": 10,
        "keep_jsonl_lines": 1000,
    },
    "indexing": {
        "exclude_dirs": [
            ".git",
            ".llmc",
            ".venv",
            "__pycache__",
            "node_modules",
            "dist",
            "build",
            ".pytest_cache",
            ".mypy_cache",
        ]
    },
    "embeddings": {
        "default_profile": "docs",
        "profiles": {"docs": {"provider": "ollama", "model": "nomic-embed-text", "dimension": 768}},
    },
    "rag": {"enabled": True},
}


@app.command()
def init(
    path: Path = typer.Option(
        ".", "--path", "-p", help="Path to initialize the workspace in (default: current directory)"
    ),
):
    """
    Bootstrap .llmc/ workspace and configuration.
    """
    # Determine root
    if path == Path("."):
        # Try to find existing root first to avoid nesting .llmc inside .llmc
        try:
            repo_root = find_repo_root()
            if repo_root == Path("."):
                # If find_repo_root returned cwd because it failed, use cwd
                target_root = Path.cwd()
            else:
                target_root = repo_root
        except Exception:
            target_root = Path.cwd()
    else:
        target_root = path.resolve()

    typer.echo(f"Initializing LLMC workspace in: {target_root}")

    # 1. Create .llmc/ directory
    llmc_dir = target_root / ".llmc"
    llmc_dir.mkdir(parents=True, exist_ok=True)

    # 2. Create logs directory
    logs_dir = llmc_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 3. Create llmc.toml if missing
    config_path = target_root / "llmc.toml"
    if not config_path.exists():
        typer.echo(f"Creating default configuration: {config_path}")
        with open(config_path, "wb") as f:
            tomli_w.dump(DEFAULT_CONFIG, f)
    else:
        typer.echo(f"Configuration already exists: {config_path}")

    # 4. Initialize DB
    # Read config to find index path
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        index_rel_path = config.get("storage", {}).get("index_path", ".llmc/index_v2.db")
        index_path = target_root / index_rel_path

        typer.echo(f"Initializing database: {index_path}")
        # Database(__init__) creates the file and schema
        db = Database(index_path)
        db.close()

    except Exception as e:
        typer.echo(f"Error initializing database: {e}", err=True)
        raise typer.Exit(code=1)

    typer.echo("✨ LLMC workspace initialized successfully.")
