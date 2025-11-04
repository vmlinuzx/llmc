from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click

from . import config, manager


def _read_text(path: Path | None, stdin_fallback: bool = False) -> str:
    if path is None:
        if stdin_fallback:
            return click.get_text_stream("stdin").read()
        raise click.UsageError("Prompt file is required.")
    if str(path) == "-":
        return click.get_text_stream("stdin").read()
    return path.read_text(encoding="utf-8")


@click.group()
def cli() -> None:
    """Semantic cache utility."""


@cli.command()
@click.option("--route", required=True, help="Route identifier (local/api/codex/etc.).")
@click.option("--provider", default=None, help="Model/provider recorded with the entry.")
@click.option(
    "--prompt-file",
    type=click.Path(path_type=Path),
    default="-",
    help="Path to the prompt (default: stdin).",
)
@click.option(
    "--min-score",
    type=float,
    default=None,
    help="Minimum cosine similarity required to accept a hit (default: env or 0.92).",
)
def lookup(route: str, provider: Optional[str], prompt_file: Path, min_score: Optional[float]) -> None:
    """Lookup a cached response."""
    prompt = _read_text(prompt_file, stdin_fallback=True)
    hit, entry = manager.lookup(prompt, route, provider=provider, min_score=min_score)
    if not hit or entry is None:
        click.echo(json.dumps({"hit": False}))
        return
    payload = {
        "hit": True,
        "score": entry.score,
        "route": entry.route,
        "provider": entry.provider,
        "response": entry.response,
        "created_at": entry.created_at,
        "tokens_in": entry.tokens_in,
        "tokens_out": entry.tokens_out,
        "total_cost": entry.total_cost,
    }
    click.echo(json.dumps(payload, ensure_ascii=False))


@cli.command()
@click.option("--route", required=True, help="Route identifier (local/api/codex/etc.).")
@click.option("--provider", default=None, help="Model/provider recorded with the entry.")
@click.option("--user-prompt", default=None, help="Original user prompt (for logging).")
@click.option(
    "--prompt-file",
    type=click.Path(path_type=Path),
    default="-",
    help="Path to the prompt text (default: stdin).",
)
@click.option(
    "--response-file",
    type=click.Path(path_type=Path),
    default=None,
    help="File containing the LLM response (default: stdin).",
)
@click.option("--tokens-in", type=int, default=None, help="Input token count.")
@click.option("--tokens-out", type=int, default=None, help="Output token count.")
@click.option("--total-cost", type=float, default=None, help="Total cost of the call.")
def store(
    route: str,
    provider: Optional[str],
    user_prompt: Optional[str],
    prompt_file: Path,
    response_file: Optional[Path],
    tokens_in: Optional[int],
    tokens_out: Optional[int],
    total_cost: Optional[float],
) -> None:
    """Store a response in the semantic cache."""
    prompt = _read_text(prompt_file, stdin_fallback=True)
    response = _read_text(response_file, stdin_fallback=True)
    manager.store(
        prompt,
        response,
        route,
        provider=provider,
        user_prompt=user_prompt,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        total_cost=total_cost,
    )
    click.echo(json.dumps({"stored": True}))


@cli.command()
def stats() -> None:
    """Show cache statistics."""
    if not config.cache_enabled():
        click.echo(json.dumps({"enabled": False}))
        return
    repo = Path.cwd()
    db_path = config.cache_db_path(repo)
    if not db_path.exists():
        click.echo(json.dumps({"enabled": True, "entries": 0}))
        return

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        total = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    except sqlite3.DatabaseError:
        total = 0
    finally:
        conn.close()
    click.echo(json.dumps({"enabled": True, "entries": total}))


if __name__ == "__main__":
    cli()
