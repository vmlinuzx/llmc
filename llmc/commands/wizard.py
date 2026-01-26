"""
Interactive Configuration Wizard for LLMC.

Guides users through setup:
1. Ollama discovery & connectivity check
2. Model selection (Enrichment & Embeddings)
3. Config generation & validation
"""

from pathlib import Path

import requests
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
import tomli_w
import typer

# Try to import tomllib (Python 3.11+) or fall back to tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


console = Console()

# Recommended models for different tiers
# Note: qwen3 significantly outperforms qwen2.5 at comparable sizes
# (qwen3:4b generally beats qwen2.5:14b on coding tasks)
RECOMMENDED_SMALL = [
    "qwen3:4b",
    "qwen3:4b-instruct",
    "qwen3:1.7b",
    "llama3.2:3b",
    "qwen2.5:3b",
]
RECOMMENDED_MEDIUM = [
    "qwen3:8b",
    "qwen3:8b-instruct",
    "qwen2.5:7b",
    "llama3.1:8b",
    "gemma2:9b",
]
RECOMMENDED_LARGE = [
    "qwen3:14b",
    "qwen3:32b",
    "qwen2.5:14b",
    "qwen2.5:32b",
    "llama3.3:70b",
]
RECOMMENDED_EMBED = [
    "nomic-embed-text",
    "mxbai-embed-large",
    "all-minilm",
    "snowflake-arctic-embed",
]


def _check_ollama(url: str) -> tuple[bool, list[str]]:
    """Check Ollama connectivity and return available models."""
    try:
        # Normalize URL
        url = url.rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"

        # Check tags endpoint
        resp = requests.get(f"{url}/api/tags", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            return True, models
    except Exception:
        pass
    return False, []


def _print_model_table(models: list[str], current_selection: str | None = None):
    """Print available models in a table."""
    table = Table(title="Available Models")
    table.add_column("Model Name", style="cyan")
    table.add_column("Size", style="dim")
    table.add_column("Family", style="green")

    # Sort models nicely
    models.sort()

    for model in models:
        # Heuristics for display
        style = ""
        if current_selection and model == current_selection:
            style = "bold yellow"

        # Try to guess family/size (very basic)
        parts = model.split(":")
        name = parts[0]
        tag = parts[1] if len(parts) > 1 else "latest"

        table.add_row(model, tag, name, style=style)

    console.print(table)


def _select_model(
    prompt_text: str,
    models: list[str],
    recommended: list[str],
    allow_skip: bool = False,
    default: str | None = None,
) -> str | None:
    """Ask user to select a model with autocomplete-like suggestions."""

    # Filter available recommendations
    available_recs = [r for r in recommended if any(r in m for m in models)]

    # Suggest a default
    suggestion = default
    if not suggestion and available_recs:
        # Find the exact match in models corresponding to the recommendation
        for rec in available_recs:
            matches = [m for m in models if rec in m or m in rec]
            if matches:
                suggestion = matches[0]
                break

    if not suggestion and models:
        suggestion = models[0]

    console.print(f"\n[bold]{prompt_text}[/bold]")
    if available_recs:
        console.print(f"Recommended: [green]{', '.join(available_recs)}[/green]")

    choices = models[:]
    if allow_skip:
        choices.append("skip")

    while True:
        selection = Prompt.ask(
            "Select model",
            choices=(
                choices if len(choices) < 20 else None
            ),  # Don't list all if too many
            default=suggestion if suggestion else None,
        )

        if selection == "skip" and allow_skip:
            return None

        if selection in models:
            return selection

        # Allow partial match if unique
        matches = [m for m in models if selection in m]
        if len(matches) == 1:
            console.print(f"Did you mean [cyan]{matches[0]}[/cyan]?")
            if Confirm.ask("Use this model?"):
                return matches[0]

        console.print(
            "[red]Invalid selection. Please choose from available models.[/red]"
        )


def run_wizard(
    repo_path: Path = Path("."),
    models_only: bool = False,
):
    """Run the interactive configuration wizard."""
    console.print(Panel.fit("[bold blue]LLMC Interactive Config Wizard[/bold blue]"))

    repo_path = repo_path.resolve()
    console.print(f"Configuring repository: [dim]{repo_path}[/dim]\n")

    config_path = repo_path / "llmc.toml"
    existing_config = {}

    if models_only:
        if not config_path.exists():
            console.print(f"[red]❌ Config file not found: {config_path}[/red]")
            console.print("Cannot run --models-only without existing config.")
            raise typer.Exit(1)

        if tomllib:
            try:
                with open(config_path, "rb") as f:
                    existing_config = tomllib.load(f)
            except Exception as e:
                console.print(f"[red]❌ Failed to parse config: {e}[/red]")
                raise typer.Exit(1) from None
        else:
            console.print(
                "[red]❌ No TOML parser available (install tomli or use Python 3.11+)[/red]"
            )
            raise typer.Exit(1)

        console.print("[bold]Updating model configuration only.[/bold]")

    # 1. Ollama Setup
    console.print("[bold]1. Ollama Configuration[/bold]")

    # If existing config has Ollama URL, suggest it
    default_url = "http://localhost:11434"
    if existing_config:
        try:
            # Try to find URL in existing chains
            for chain in existing_config.get("enrichment", {}).get("chain", []):
                if chain.get("url"):
                    default_url = chain.get("url")
                    break
        except Exception:
            pass

    ollama_url = Prompt.ask("Ollama URL", default=default_url)

    with console.status(f"Connecting to {ollama_url}..."):
        connected, models = _check_ollama(ollama_url)

    if not connected:
        console.print(f"[bold red]❌ Could not connect to {ollama_url}[/bold red]")
        if not Confirm.ask("Continue anyway? (You'll need to fix connectivity later)"):
            raise typer.Exit(1)
        models = []
    else:
        console.print(f"[green]✅ Connected! Found {len(models)} models.[/green]")

    if not models and connected:
        console.print(
            "[yellow]⚠️  No models found in Ollama. You'll need to pull some models first.[/yellow]"
        )
        console.print("Example: [dim]ollama pull qwen3:4b[/dim]")

    # 2. Model Selection
    console.print("\n[bold]2. Enrichment Model Selection[/bold]")
    console.print(
        "LLMC uses a tiered approach: Fast models for simple files, larger models for complex ones."
    )

    # Tier 1: Small/Fast
    tier1_model = _select_model(
        "Select PRIMARY model (Small/Fast - e.g. 1b-4b params)",
        models,
        RECOMMENDED_SMALL,
        default="qwen3:4b",
    )

    # Tier 2: Medium (Optional)
    tier2_model = None
    if tier1_model:
        tier2_model = _select_model(
            "Select FALLBACK model (Medium - e.g. 7b-9b params)",
            models,
            RECOMMENDED_MEDIUM,
            allow_skip=True,
            default="qwen3:8b",
        )

    # Tier 3: Large (Optional)
    tier3_model = None
    if tier2_model:
        tier3_model = _select_model(
            "Select FINAL FALLBACK model (Large - e.g. 14b+ params)",
            models,
            RECOMMENDED_LARGE,
            allow_skip=True,
            default="qwen3:14b",
        )

    # 3. Embeddings
    console.print("\n[bold]3. Embeddings Configuration[/bold]")
    embed_model = _select_model(
        "Select EMBEDDING model", models, RECOMMENDED_EMBED, default="nomic-embed-text"
    )

    # 4. Generate Config
    console.print("\n[bold]4. Generating Configuration[/bold]")

    if models_only:
        config = existing_config
    else:
        # Construct default config
        config = {
            "storage": {"index_path": ".rag/index_v2.db"},
            "logging": {
                "log_directory": ".llmc/logs",
                "enable_rotation": True,
                "max_file_size_mb": 10,
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
                ]
            },
            "rag": {"enabled": True},
        }

    # Build Enrichment Chain
    chain = []

    if tier1_model:
        chain.append(
            {
                "name": f"{tier1_model.split(':')[0]}-fast",
                "chain": "code_enrichment_models",
                "provider": "ollama",
                "model": tier1_model,
                "url": ollama_url,
                "routing_tier": "fast",
                "timeout_seconds": 90,
                "enabled": True,
                "options": {"num_ctx": 8192, "temperature": 0.2},
            }
        )

    if tier2_model:
        chain.append(
            {
                "name": f"{tier2_model.split(':')[0]}-medium",
                "chain": "code_enrichment_models",
                "provider": "ollama",
                "model": tier2_model,
                "url": ollama_url,
                "routing_tier": "medium",
                "timeout_seconds": 120,
                "enabled": True,
                "options": {"num_ctx": 8192, "temperature": 0.2},
            }
        )

    if tier3_model:
        chain.append(
            {
                "name": f"{tier3_model.split(':')[0]}-large",
                "chain": "code_enrichment_models",
                "provider": "ollama",
                "model": tier3_model,
                "url": ollama_url,
                "routing_tier": "large",
                "timeout_seconds": 180,
                "enabled": True,
                "options": {"num_ctx": 12288, "temperature": 0.2},
            }
        )

    # Update enrichment section
    if "enrichment" not in config:
        config["enrichment"] = {
            "default_chain": "code_enrichment_models",
            "batch_size": 50,
            "est_tokens_per_span": 350,
            "enforce_latin1_enrichment": True,
            "max_failures_per_span": 4,
            "enable_routing": True,
            "routes": {
                "docs": "code_enrichment_models",
                "code": "code_enrichment_models",
            },
        }

    config["enrichment"]["chain"] = chain

    # Build Embeddings Config
    if "embeddings" not in config:
        config["embeddings"] = {
            "default_profile": "docs",
            "profiles": {},
            "routes": {
                "docs": {"profile": "docs", "index": "embeddings"},
                "code": {"profile": "docs", "index": "embeddings"},
            },
        }

    # Ensure profiles dict exists
    if "profiles" not in config["embeddings"]:
        config["embeddings"]["profiles"] = {}

    config["embeddings"]["profiles"]["docs"] = {
        "provider": "ollama",
        "model": embed_model or "nomic-embed-text",
        "dimension": 768,
        "ollama": {
            "api_base": ollama_url,
            "timeout": 120,
        },
    }

    if not models_only:
        config["routing"] = {
            "slice_type_to_route": {
                "code": "code",
                "docs": "docs",
                "config": "docs",
                "data": "docs",
                "other": "docs",
            },
        }

    # Review
    console.print(
        Panel(
            f"Primary: {tier1_model}\n"
            f"Fallback: {tier2_model or 'None'}\n"
            f"Final: {tier3_model or 'None'}\n"
            f"Embeddings: {embed_model}",
            title="Config Summary",
        )
    )

    # Save
    if config_path.exists() and not models_only:
        if not Confirm.ask(f"Overwrite existing {config_path}?"):
            console.print("Cancelled.")
            return

    try:
        with open(config_path, "wb") as f:
            tomli_w.dump(config, f)
        console.print(f"[green]✨ Configuration saved to {config_path}[/green]")
    except Exception as e:
        console.print(f"[red]❌ Failed to save config: {e}[/red]")
        raise typer.Exit(1) from None

    # Validate
    if Confirm.ask("Run validation now?"):
        from llmc.commands.repo_validator import print_result, validate_repo

        result = validate_repo(repo_path, check_connectivity=True, check_models=True)
        print_result(result)
        if result.passed:
            console.print("\n[bold green]🚀 You are ready to go![/bold green]")
            if not models_only:
                console.print(
                    "Run: [cyan]llmc repo register .[/cyan] (if not already registered)"
                )
            console.print("Run: [cyan]llmc service start[/cyan]")


if __name__ == "__main__":
    typer.run(run_wizard)
