"""
Service management commands for LLMC RAG service.

Delegates to existing tools.rag.service_daemon infrastructure.
"""

from pathlib import Path

import typer

from llmc.core import find_repo_root

# Import existing service infrastructure
try:
    from llmc.rag.service import ServiceState
    from llmc.rag.service_daemon import SystemdManager
except ImportError:
    # Graceful degradation if imports fail
    SystemdManager = None
    ServiceState = None

# Import RAG doctor and quality for health checks
try:
    from llmc.rag.doctor import run_rag_doctor
    from llmc.rag.quality import run_quality_check
except ImportError:
    run_rag_doctor = None
    run_quality_check = None


def _get_manager():
    """Get SystemdManager instance or exit with error."""
    if SystemdManager is None:
        typer.echo("Error: Service infrastructure not available", err=True)
        raise typer.Exit(code=1)

    repo_root = find_repo_root()
    return SystemdManager(repo_root)


def _get_state():
    """Get ServiceState instance or exit with error."""
    if ServiceState is None:
        typer.echo("Error: Service state management not available", err=True)
        raise typer.Exit(code=1)

    return ServiceState()


def start(
    interval: int = typer.Option(180, help="Enrichment cycle interval in seconds"),
):
    """Start the RAG service daemon."""
    manager = _get_manager()
    state = _get_state()

    # Check if repos are registered
    if not state.state.get("repos"):
        typer.echo("❌ No repos registered. Use 'llmc service repo add <path>' first.")
        raise typer.Exit(code=1)

    # Check if systemd is available
    if not manager.is_systemd_available():
        typer.echo("⚠️  Systemd not available - service management requires systemd")
        typer.echo("   Run 'llmc-rag start' for fallback fork() mode")
        raise typer.Exit(code=1)

    # Check if already running
    status = manager.status()
    if status["running"]:
        typer.echo(f"✅ Service already running (PID {status['pid']})")
        return

    # Update interval in state
    state.state["interval"] = interval
    state.save()

    # Start via systemd
    success, message = manager.start()
    if not success:
        typer.echo(f"❌ Failed to start: {message}", err=True)
        raise typer.Exit(code=1)

    # Verify startup (give it 2 seconds)
    import time

    time.sleep(2)
    status = manager.status()

    if not status["running"]:
        typer.echo("❌ Service failed to start", err=True)
        typer.echo("📋 Check logs: llmc service logs")
        raise typer.Exit(code=1)

    typer.echo(f"🚀 Service started (PID {status['pid']})")
    typer.echo(f"   Tracking {len(state.state['repos'])} repos")
    typer.echo(f"   Interval: {interval}s")
    typer.echo("\n📋 View logs: llmc service logs -f")


def stop():
    """Stop the RAG service daemon."""
    manager = _get_manager()

    if not manager.is_systemd_available():
        typer.echo("⚠️  Systemd not available")
        typer.echo("   Use 'llmc-rag stop' for fallback mode")
        raise typer.Exit(code=1)

    status = manager.status()
    if not status["running"]:
        typer.echo("Service is not running")
        return

    success, message = manager.stop()
    if success:
        typer.echo(f"✅ {message}")
    else:
        typer.echo(f"❌ Failed to stop: {message}", err=True)
        raise typer.Exit(code=1)


def restart(
    interval: int = typer.Option(None, help="Update enrichment cycle interval"),
):
    """Restart the RAG service daemon."""
    manager = _get_manager()
    state = _get_state()

    if not manager.is_systemd_available():
        typer.echo("⚠️  Systemd not available")
        raise typer.Exit(code=1)

    # Update interval if provided
    if interval is not None:
        state.state["interval"] = interval
        state.save()
        typer.echo(f"Updated interval to {interval}s")

    success, message = manager.restart()
    if success:
        typer.echo(f"✅ {message}")

        # Show status after restart
        import time

        time.sleep(1)
        status = manager.status()
        if status["running"]:
            typer.echo(f"   PID: {status['pid']}")
    else:
        typer.echo(f"❌ Failed to restart: {message}", err=True)
        raise typer.Exit(code=1)


def status():
    """Show service status and registered repos."""
    manager = _get_manager()
    state = _get_state()

    if not manager.is_systemd_available():
        typer.echo("⚠️  Systemd not available")
        # Still show state info
        typer.echo(f"\nRegistered repos: {len(state.state.get('repos', []))}")
        for repo in state.state.get("repos", []):
            typer.echo(f"  • {repo}")
        return

    svc_status = manager.status()

    # Service status
    if svc_status["running"]:
        typer.echo(f"✅ Service: RUNNING (PID {svc_status['pid']})")
    elif svc_status.get("active"):
        typer.echo("⚠️  Service: ACTIVE but not running")
    else:
        typer.echo("❌ Service: STOPPED")

    # Repo info with health status
    repos = state.state.get("repos", [])
    typer.echo(f"\n📂 Registered repos: {len(repos)}")
    
    for repo in repos:
        repo_path = Path(repo)
        repo_name = repo_path.name
        
        # Get health info if available
        health_line = _get_repo_health_summary(repo_path)
        
        typer.echo(f"   • {repo}")
        if health_line:
            typer.echo(f"     {health_line}")

    # Cycle info
    interval = state.state.get("interval", 180)
    last_cycle = state.state.get("last_cycle")
    typer.echo(f"\n⏱️  Interval: {interval}s")
    if last_cycle:
        typer.echo(f"   Last cycle: {last_cycle}")

    # Show brief systemctl status if running
    if svc_status["running"] and "status_text" in svc_status:
        typer.echo("\n📊 Systemd Status:")
        # Show just the Active line
        for line in svc_status["status_text"].split("\n"):
            if "Active:" in line or "Main PID:" in line:
                typer.echo(f"   {line.strip()}")


def _get_repo_health_summary(repo_path: Path) -> str:
    """Get a compact health summary for a single repo."""
    if run_rag_doctor is None:
        return ""
    
    try:
        # Get doctor report
        report = run_rag_doctor(repo_path)
        status = report.get("status", "UNKNOWN")
        stats = report.get("stats")
        
        if status == "NO_DB":
            return "⚪ No index (run: llmc repo add)"
        
        if stats is None:
            return "❓ Unable to read stats"
        
        files = stats.get("files", 0)
        spans = stats.get("spans", 0)
        enrichments = stats.get("enrichments", 0)
        embeddings = stats.get("embeddings", 0)
        pending_enrichments = stats.get("pending_enrichments", 0)
        pending_embeddings = stats.get("pending_embeddings", 0)
        
        # Calculate enrichment percentage
        enrich_pct = (enrichments / spans * 100) if spans > 0 else 0
        embed_pct = (embeddings / spans * 100) if spans > 0 else 0
        
        # Get quality score if available
        quality_str = ""
        if run_quality_check is not None and enrichments > 0:
            try:
                quality = run_quality_check(repo_path)
                if quality.get("status") not in ("NO_DB", "EMPTY"):
                    qscore = quality.get("quality_score", 0)
                    q_emoji = "✅" if qscore >= 90 else "⚠️" if qscore >= 70 else "❌"
                    quality_str = f" | Quality: {q_emoji} {qscore:.0f}%"
            except Exception:
                pass
        
        # Status emoji
        if status == "OK":
            status_emoji = "✅"
        elif status == "WARN":
            status_emoji = "⚠️"
        elif status == "EMPTY":
            status_emoji = "📭"
        else:
            status_emoji = "❓"
        
        # Pending work indicator
        pending_str = ""
        if pending_enrichments > 0 or pending_embeddings > 0:
            pending_parts = []
            if pending_enrichments > 0:
                pending_parts.append(f"{pending_enrichments} enrich")
            if pending_embeddings > 0:
                pending_parts.append(f"{pending_embeddings} embed")
            pending_str = f" | Pending: {', '.join(pending_parts)}"
        
        return (
            f"{status_emoji} {files} files, {spans} spans | "
            f"Enriched: {enrich_pct:.0f}% | Embedded: {embed_pct:.0f}%"
            f"{quality_str}{pending_str}"
        )
        
    except Exception as e:
        return f"❌ Error checking health: {e}"




def logs(
    follow: bool = typer.Option(False, "-f", "--follow", help="Follow log output"),
    lines: int = typer.Option(50, "-n", "--lines", help="Number of lines to show"),
):
    """View service logs via journalctl."""
    manager = _get_manager()

    if not manager.is_systemd_available():
        typer.echo("⚠️  Systemd not available - no journal logs")
        typer.echo("   Check ~/.llmc/logs/rag-daemon/rag-service.log for fallback logs")
        raise typer.Exit(code=1)

    if follow:
        # Stream logs (blocking)
        proc = manager.get_logs(lines=lines, follow=True)
        if proc:
            try:
                proc.wait()
            except KeyboardInterrupt:
                proc.terminate()
                typer.echo("\n")
    else:
        # Show logs and exit
        manager.get_logs(lines=lines, follow=False)


def enable():
    """Enable service to start on user login."""
    manager = _get_manager()

    if not manager.is_systemd_available():
        typer.echo("⚠️  Systemd not available")
        raise typer.Exit(code=1)

    success, message = manager.enable()
    if success:
        typer.echo(f"✅ {message}")
    else:
        typer.echo(f"❌ Failed to enable: {message}", err=True)
        raise typer.Exit(code=1)


def disable():
    """Disable service from starting on user login."""
    manager = _get_manager()

    if not manager.is_systemd_available():
        typer.echo("⚠️  Systemd not available")
        raise typer.Exit(code=1)

    success, message = manager.disable()
    if success:
        typer.echo(f"✅ {message}")
    else:
        typer.echo(f"❌ Failed to disable: {message}", err=True)
        raise typer.Exit(code=1)


def repo_add(
    path: str = typer.Argument(..., help="Repository path to register"),
):
    """Register a repository for enrichment."""
    state = _get_state()

    repo_path = Path(path).resolve()
    if not repo_path.exists():
        typer.echo(f"❌ Path does not exist: {path}", err=True)
        raise typer.Exit(code=1)

    if not (repo_path / ".git").exists():
        typer.echo(f"⚠️  Warning: {path} is not a git repository")

    if state.add_repo(str(repo_path)):
        typer.echo(f"✅ Registered: {repo_path}")
        typer.echo(f"   Total repos: {len(state.state['repos'])}")
    else:
        typer.echo(f"ℹ️  Already registered: {repo_path}")


def repo_remove(
    path: str = typer.Argument(..., help="Repository path to unregister"),
):
    """Unregister a repository from enrichment."""
    state = _get_state()

    repo_path = Path(path).resolve()

    if state.remove_repo(str(repo_path)):
        typer.echo(f"✅ Unregistered: {repo_path}")
        typer.echo(f"   Total repos: {len(state.state['repos'])}")
    else:
        typer.echo(f"❌ Not registered: {repo_path}", err=True)
        raise typer.Exit(code=1)


def repo_list():
    """List all registered repositories."""
    state = _get_state()

    repos = state.state.get("repos", [])
    if not repos:
        typer.echo("No repositories registered")
        typer.echo("\nAdd a repo: llmc service repo add <path>")
        return

    typer.echo(f"Registered repositories ({len(repos)}):\n")
    for i, repo in enumerate(repos, 1):
        typer.echo(f"{i}. {repo}")
