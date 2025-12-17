"""
CLI commands for documentation generation.

Heavy imports (DocgenOrchestrator, Database) are deferred to function-level
to prevent import-time failures when [rag] extras are not installed.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import toml
import typer

from llmc.docgen.config import get_output_dir, get_require_rag_fresh, load_docgen_backend

if TYPE_CHECKING:
    from llmc.docgen.orchestrator import DocgenOrchestrator
    from llmc.rag.database import Database

logger = logging.getLogger(__name__)

app = typer.Typer(help="Documentation generation commands")


@app.command()
def generate(
    path: str | None = typer.Argument(None, help="Path to file to generate docs for"),
    all: bool = typer.Option(False, "--all", help="Generate docs for all indexed files"),
    force: bool = typer.Option(False, "--force", help="Force generation (ignore SHA gate)"),
):
    """Generate documentation for repository files."""
    
    # Get repo root
    repo_root = Path.cwd()
    
    # Load config
    config_path = repo_root / "llmc.toml"
    if not config_path.exists():
        typer.echo(f"❌ Config not found: {config_path}", err=True)
        raise typer.Exit(1)
    
    with open(config_path) as f:
        toml_data = toml.load(f)
    
    # Load backend
    backend = load_docgen_backend(repo_root, toml_data)
    if backend is None:
        typer.echo("❌ Docgen is disabled in configuration", err=True)
        typer.echo("💡 Enable it by setting [docs.docgen] enabled = true", err=True)
        raise typer.Exit(1)
    
    # Load database - try multiple locations
    # Load database - try multiple locations
    candidates = [
        repo_root / ".rag" / "index_v2.db",
        repo_root / ".llmc" / "index_v2.db",
        repo_root / ".llmc" / "rag" / "index.db",
    ]
    
    db_path = None
    for p in candidates:
        if p.exists():
            db_path = p
            break
            
    if not db_path:
        typer.echo(f"❌ RAG database not found. Searched: {[str(p) for p in candidates]}", err=True)
        typer.echo("💡 Run `llmc index` first to index the repository", err=True)
        raise typer.Exit(1)
    
    # Deferred import to allow CLI to load without [rag] extras
    from llmc.rag.database import Database
    db = Database(db_path)
    
    # Get config settings
    output_dir = get_output_dir(toml_data)
    require_rag_fresh = get_require_rag_fresh(toml_data)
    
    # Deferred import to allow CLI to load without [rag] extras
    from llmc.docgen.orchestrator import DocgenOrchestrator
    
    # Create orchestrator
    orchestrator = DocgenOrchestrator(
        repo_root=repo_root,
        backend=backend,
        db=db,
        output_dir=output_dir,
        require_rag_fresh=require_rag_fresh,
    )
    
    # Discover files to process
    if all:
        typer.echo("🔍 Discovering files from RAG database...")
        file_paths = _discover_all_files(db)
        typer.echo(f"📄 Found {len(file_paths)} indexed files")
    elif path:
        # Normalize path: if absolute and inside repo, convert to relative
        input_path = Path(path)
        if input_path.is_absolute():
            try:
                # Try to make it relative to repo_root
                relative_path = input_path.resolve().relative_to(repo_root.resolve())
                file_paths = [relative_path]
            except ValueError:
                # Path is outside repo, keep as-is (will likely fail later, but with clearer error)
                typer.echo("⚠️  Warning: Path appears to be outside repository root", err=True)
                file_paths = [input_path]
        else:
            # Already relative, use as-is
            file_paths = [input_path]
    else:
        typer.echo("❌ Either --all or PATH must be specified", err=True)
        raise typer.Exit(1)
    
    # Process files
    typer.echo(f"⚙️  Processing {len(file_paths)} files...")
    results = orchestrator.process_batch(file_paths, force=force)
    
    # Print summary
    total = len(results)
    generated = sum(1 for r in results.values() if r.status == "generated")
    noop = sum(1 for r in results.values() if r.status == "noop")
    skipped = sum(1 for r in results.values() if r.status == "skipped")
    
    typer.echo("")
    typer.echo("📊 Summary:")
    typer.echo(f"  Total files:     {total}")
    typer.echo(f"  ✅ Generated:    {generated}")
    typer.echo(f"  ⏭️  No-op:         {noop}")
    typer.echo(f"  ⏸️  Skipped:      {skipped}")
    
    if generated > 0:
        typer.echo(f"\n✨ Documentation written to {output_dir}/")


@app.command()
def status():
    """Show documentation generation status."""
    
    # Get repo root
    repo_root = Path.cwd()
    
    # Load config
    config_path = repo_root / "llmc.toml"
    if not config_path.exists():
        typer.echo(f"❌ Config not found: {config_path}", err=True)
        raise typer.Exit(1)
    
    with open(config_path) as f:
        toml_data = toml.load(f)
    
    # Check if docgen is enabled
    backend = load_docgen_backend(repo_root, toml_data)
    enabled = backend is not None
    
    output_dir = get_output_dir(toml_data)
    require_rag = get_require_rag_fresh(toml_data)
    
    # Load database
    # Load database - try multiple locations
    candidates = [
        repo_root / ".rag" / "index_v2.db",
        repo_root / ".llmc" / "index_v2.db",
        repo_root / ".llmc" / "rag" / "index.db",
    ]
    
    db_path = None
    for p in candidates:
        if p.exists():
            db_path = p
            break

    if not db_path:
        typer.echo("❌ RAG database not found", err=True)
        raise typer.Exit(1)
    
    # Deferred import to allow CLI to load without [rag] extras
    from llmc.rag.database import Database
    db = Database(db_path)
    
    # Get stats
    stats = db.stats()
    total_files = stats["files"]
    
    # Count docs
    docs_dir = repo_root / output_dir
    doc_count = 0
    if docs_dir.exists():
        doc_count = len(list(docs_dir.rglob("*.md")))
    
    # Print status
    typer.echo("📊 Docgen Status")
    typer.echo("=" * 50)
    typer.echo(f"Enabled:          {enabled}")
    typer.echo(f"Output directory: {output_dir}")
    typer.echo(f"Require RAG fresh: {require_rag}")
    typer.echo("")
    typer.echo(f"Files in RAG:     {total_files}")
    typer.echo(f"Docs generated:   {doc_count}")
    typer.echo(f"Coverage:         {doc_count}/{total_files} ({100*doc_count//max(total_files,1)}%)")


def _discover_all_files(db: "Database") -> list[Path]:
    """Discover all files in RAG database.
    
    Args:
        db: Database instance
        
    Returns:
        List of file paths relative to repo root
    """
    rows = db.conn.execute("SELECT path FROM files").fetchall()
    return [Path(row[0]) for row in rows]


if __name__ == "__main__":
    app()
