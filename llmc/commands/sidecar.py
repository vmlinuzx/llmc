"""
CLI commands for managing document sidecars.

Commands:
- llmc sidecar list: Show all sidecars and their freshness status
- llmc sidecar clean: Remove orphaned sidecars
- llmc sidecar generate: Force regenerate sidecar for a file/directory
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table
import typer

from llmc.core import find_repo_root

app = typer.Typer(help="Manage document sidecars (PDF, DOCX → markdown conversion)")
console = Console()


def _get_sidecar_module():
    """Lazy import of sidecar module."""
    try:
        from llmc.rag.sidecar import (
            SidecarConverter,
            cleanup_orphan_sidecars,
            get_sidecar_path,
            is_sidecar_eligible,
            is_sidecar_stale,
        )
        return {
            "SidecarConverter": SidecarConverter,
            "cleanup_orphan_sidecars": cleanup_orphan_sidecars,
            "get_sidecar_path": get_sidecar_path,
            "is_sidecar_eligible": is_sidecar_eligible,
            "is_sidecar_stale": is_sidecar_stale,
        }
    except ImportError as e:
        console.print(f"[red]Error: Sidecar module not available: {e}[/red]")
        raise typer.Exit(1) from None


@app.command("list")
def list_sidecars(
    path: str | None = typer.Argument(None, help="Limit to specific directory"),
):
    """List all document sidecars and their freshness status."""
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Error: Not in a repository[/red]")
        raise typer.Exit(1) from None

    mod = _get_sidecar_module()

    sidecars_dir = repo_root / ".llmc" / "sidecars"
    if not sidecars_dir.exists():
        console.print("[dim]No sidecars found.[/dim]")
        return

    table = Table(title="Document Sidecars")
    table.add_column("Source File", style="cyan")
    table.add_column("Sidecar", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Size")

    total = 0
    fresh = 0
    stale = 0
    orphan = 0

    for sidecar in sorted(sidecars_dir.rglob("*.md.gz")):
        # Reconstruct source path
        try:
            rel_sidecar = sidecar.relative_to(sidecars_dir)
            source_rel = str(rel_sidecar).removesuffix(".md.gz")
            source_path = repo_root / source_rel

            # Filter by path if specified
            if path:
                if not source_rel.startswith(path):
                    continue

            # Determine status
            if not source_path.exists():
                status = "[red]ORPHAN[/red]"
                orphan += 1
            elif mod["is_sidecar_stale"](Path(source_rel), repo_root):
                status = "[yellow]STALE[/yellow]"
                stale += 1
            else:
                status = "[green]FRESH[/green]"
                fresh += 1

            total += 1

            # Get sidecar size
            size_kb = sidecar.stat().st_size / 1024

            table.add_row(
                source_rel,
                str(sidecar.relative_to(repo_root)),
                status,
                f"{size_kb:.1f} KB",
            )
        except Exception as e:
            console.print(f"[dim]Error processing {sidecar}: {e}[/dim]")

    if total > 0:
        console.print(table)
        console.print(
            f"\n[bold]Summary:[/bold] {total} sidecars "
            f"([green]{fresh} fresh[/green], [yellow]{stale} stale[/yellow], [red]{orphan} orphan[/red])"
        )
    else:
        console.print("[dim]No sidecars found.[/dim]")


@app.command("clean")
def clean_orphans(
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would be removed"),
):
    """Remove orphaned sidecars (source files no longer exist)."""
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Error: Not in a repository[/red]")
        raise typer.Exit(1) from None

    mod = _get_sidecar_module()

    sidecars_dir = repo_root / ".llmc" / "sidecars"
    if not sidecars_dir.exists():
        console.print("[dim]No sidecars directory found.[/dim]")
        return

    orphans = []
    for sidecar in sidecars_dir.rglob("*.md.gz"):
        try:
            rel_sidecar = sidecar.relative_to(sidecars_dir)
            source_rel = str(rel_sidecar).removesuffix(".md.gz")
            source_path = repo_root / source_rel

            if not source_path.exists():
                orphans.append(sidecar)
        except Exception:
            pass

    if not orphans:
        console.print("[green]✓[/green] No orphaned sidecars found.")
        return

    if dry_run:
        console.print(f"Would remove {len(orphans)} orphaned sidecars:")
        for orphan in orphans:
            console.print(f"  [red]×[/red] {orphan.relative_to(repo_root)}")
    else:
        removed = mod["cleanup_orphan_sidecars"](repo_root)
        console.print(f"[green]✓[/green] Removed {removed} orphaned sidecars.")


@app.command("generate")
def generate_sidecar(
    path: str = typer.Argument(..., help="Path to document or directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Regenerate even if fresh"),
):
    """Generate or regenerate sidecar for a document or directory."""
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Error: Not in a repository[/red]")
        raise typer.Exit(1) from None

    mod = _get_sidecar_module()

    target = Path(path)
    if not target.is_absolute():
        target = repo_root / target

    if not target.exists():
        console.print(f"[red]Error: Path not found: {path}[/red]")
        raise typer.Exit(1)

    # Collect files to process
    files_to_process = []
    if target.is_file():
        if mod["is_sidecar_eligible"](target):
            files_to_process.append(target)
        else:
            console.print(f"[yellow]Skipping non-document file: {path}[/yellow]")
    else:
        # Directory - find all eligible files
        for ext in [".pdf", ".docx", ".pptx", ".rtf"]:
            for f in target.rglob(f"*{ext}"):
                if mod["is_sidecar_eligible"](f):
                    files_to_process.append(f)

    if not files_to_process:
        console.print("[dim]No eligible documents found.[/dim]")
        return

    converter = mod["SidecarConverter"]()
    generated = 0
    skipped = 0
    failed = 0

    for file_path in files_to_process:
        try:
            rel_path = file_path.relative_to(repo_root)
        except ValueError:
            rel_path = file_path

        # Check if fresh and skip if not forcing
        if not force and not mod["is_sidecar_stale"](rel_path, repo_root):
            console.print(f"[dim]Skipping (fresh): {rel_path}[/dim]")
            skipped += 1
            continue

        try:
            sidecar = converter.convert(rel_path, repo_root)
            if sidecar:
                console.print(f"[green]✓[/green] Generated: {rel_path}")
                generated += 1
            else:
                console.print(f"[yellow]⚠[/yellow] No converter: {rel_path}")
                skipped += 1
        except Exception as e:
            console.print(f"[red]✗[/red] Failed: {rel_path} ({e})")
            failed += 1

    console.print(
        f"\n[bold]Summary:[/bold] {generated} generated, {skipped} skipped, {failed} failed"
    )


if __name__ == "__main__":
    app()
