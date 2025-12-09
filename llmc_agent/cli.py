"""llmc_agent CLI entry point.

Crawl Phase: RAG-powered repo Q&A for small models.
Now with session persistence for multi-turn conversations.
"""

from __future__ import annotations

import asyncio
import os
import sys

import click
from rich.console import Console

from llmc_agent import __version__
from llmc_agent.agent import Agent
from llmc_agent.config import load_config
from llmc_agent.session import Session, SessionManager

console = Console(stderr=True)  # Metadata to stderr
stdout_console = Console()  # Main output to stdout


@click.command()
@click.argument("prompt", required=False)
@click.option("-n", "--new", is_flag=True, help="Start a new session")
@click.option("-r", "--recall", is_flag=True, help="Show last exchange")
@click.option("-l", "--list", "list_sessions", is_flag=True, help="List recent sessions")
@click.option("-s", "--session", "session_id", help="Use specific session")
@click.option("--config", "config_path", help="Config file path")
@click.option("--status", is_flag=True, help="Show status")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress metadata")
@click.option("--no-rag", is_flag=True, help="Disable RAG search")
@click.option("--no-session", is_flag=True, help="Disable session (stateless mode)")
@click.option("--model", help="Override model")
@click.option("--version", is_flag=True, help="Show version")
def main(
    prompt: str | None,
    new: bool,
    recall: bool,
    list_sessions: bool,
    session_id: str | None,
    config_path: str | None,
    status: bool,
    json_output: bool,
    quiet: bool,
    no_rag: bool,
    no_session: bool,
    model: str | None,
    version: bool,
) -> None:
    """llmc chat - AI coding assistant with RAG.
    
    \b
    Examples:
        llmc chat "where is the routing logic"     Ask about code
        llmc chat "tell me more about that"        Continue conversation
        llmc chat -n "new topic"                   Start fresh session
        llmc chat -r                               Recall last exchange
        llmc chat -l                               List recent sessions
    
    \b
    Crawl Phase (v0.1.x): RAG-powered Q&A with persistence
    "You can't edit what you can't find."
    """
    
    if version:
        click.echo(f"llmc-agent v{__version__}")
        return
    
    # Load config
    config = load_config(config_path)
    
    # Apply CLI overrides
    if no_rag:
        config.rag.enabled = False
    if model:
        config.agent.model = model
    if quiet:
        config.ui.quiet = True
    
    # Initialize session manager
    session_mgr = SessionManager(config.session.storage)
    
    # Status check
    if status:
        asyncio.run(_show_status(config, session_mgr))
        return
    
    # List sessions
    if list_sessions:
        _list_sessions(session_mgr)
        return
    
    # Recall last exchange
    if recall:
        _show_recall(session_mgr)
        return
    
    # Get prompt
    if not prompt:
        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        else:
            console.print("[dim]Usage: llmc chat \"your question here\"[/dim]")
            console.print("[dim]       llmc chat --help for more options[/dim]")
            return
    
    if not prompt:
        console.print("[red]No prompt provided[/red]")
        raise SystemExit(1)
    
    # Get or create session
    session: Session | None = None
    if not no_session:
        session = _get_or_create_session(
            session_mgr,
            config,
            new=new,
            session_id=session_id,
            quiet=quiet,
        )
    
    # Run the agent
    try:
        response = asyncio.run(_run_agent(
            prompt, config, session, session_mgr, json_output, quiet
        ))
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted[/dim]")
        raise SystemExit(130)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


def _get_or_create_session(
    session_mgr: SessionManager,
    config,
    new: bool,
    session_id: str | None,
    quiet: bool,
) -> Session:
    """Get existing session or create new one."""
    
    # Explicit session ID
    if session_id:
        session = session_mgr.load(session_id)
        if not session:
            console.print(f"[red]Session {session_id} not found[/red]")
            raise SystemExit(4)
        if not quiet:
            console.print(f"[dim]Session: {session.id} (loaded)[/dim]")
        return session
    
    # Force new session
    if new:
        session = session_mgr.create(
            model=config.agent.model,
            repo_path=os.getcwd(),
        )
        if not quiet:
            console.print(f"[dim]Session: {session.id} (new)[/dim]")
        return session
    
    # Try to resume current session
    session = session_mgr.get_current()
    
    if session:
        # Check if stale
        if session_mgr.is_stale(session, config.session.timeout_hours):
            if not quiet:
                console.print(f"[yellow]Session {session.id} is stale, starting fresh[/yellow]")
            session = session_mgr.create(
                model=config.agent.model,
                repo_path=os.getcwd(),
            )
        else:
            if not quiet:
                msg_count = len(session.messages)
                console.print(f"[dim]Session: {session.id} ({msg_count} messages)[/dim]")
    else:
        # No current session, create new
        session = session_mgr.create(
            model=config.agent.model,
            repo_path=os.getcwd(),
        )
        if not quiet:
            console.print(f"[dim]Session: {session.id} (new)[/dim]")
    
    return session


async def _run_agent(
    prompt: str,
    config,
    session: Session | None,
    session_mgr: SessionManager | None,
    json_output: bool,
    quiet: bool,
):
    """Run the agent and display results."""
    
    agent = Agent(config)
    
    # Health check
    health = await agent.health_check()
    if not health.get("ollama"):
        console.print("[red]Cannot connect to Ollama. Is it running?[/red]")
        console.print(f"[dim]Tried: {config.ollama.url}[/dim]")
        raise SystemExit(3)
    
    # Show progress if not quiet
    if not quiet and not json_output:
        rag_status = "[green]✓[/green]" if health.get("rag") else "[yellow]○[/yellow]"
        console.print(f"[dim]Model: {config.agent.model} | RAG: {rag_status}[/dim]")
    
    # Get response (with session for context)
    response = await agent.ask(prompt, session=session)
    
    # Save session
    if session and session_mgr:
        session_mgr.save(session)
    
    # Output
    if json_output:
        import json
        output = {
            "response": response.content,
            "model": response.model,
            "tokens_prompt": response.tokens_prompt,
            "tokens_completion": response.tokens_completion,
            "rag_sources": response.rag_sources,
        }
        if session:
            output["session_id"] = session.id
            output["session_messages"] = len(session.messages)
        click.echo(json.dumps(output, indent=2))
    else:
        # Metadata to stderr
        if not quiet:
            total_tokens = response.tokens_prompt + response.tokens_completion
            console.print(f"[dim]Tokens: {total_tokens} ({response.tokens_prompt}→{response.tokens_completion})[/dim]")
            
            if response.rag_sources:
                sources = response.rag_sources[:3]
                console.print(f"[dim]Sources: {', '.join(sources)}[/dim]")
        
        # Main response to stdout
        stdout_console.print(response.content)
    
    return response


def _list_sessions(session_mgr: SessionManager) -> None:
    """List recent sessions."""
    sessions = session_mgr.list_recent(10)
    
    if not sessions:
        console.print("[dim]No sessions found[/dim]")
        return
    
    current_id = session_mgr.get_current_id()
    
    console.print("[bold]Recent sessions:[/bold]")
    for s in sessions:
        # Parse timestamp for age
        try:
            from datetime import datetime, timezone
            updated = datetime.fromisoformat(s.updated_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age = now - updated
            if age.total_seconds() < 3600:
                age_str = f"{int(age.total_seconds() // 60)}m ago"
            elif age.total_seconds() < 86400:
                age_str = f"{int(age.total_seconds() // 3600)}h ago"
            else:
                age_str = f"{int(age.total_seconds() // 86400)}d ago"
        except (ValueError, TypeError):
            age_str = "?"
        
        # Preview of last message
        if s.messages:
            last = s.messages[-1]
            preview = last.content[:40] + "..." if len(last.content) > 40 else last.content
            preview = preview.replace("\n", " ")
        else:
            preview = "(empty)"
        
        marker = "*" if s.id == current_id else " "
        msg_count = len(s.messages)
        console.print(f"{marker} [bold]{s.id}[/bold] {age_str} ({msg_count} msgs) - {preview}")


def _show_recall(session_mgr: SessionManager) -> None:
    """Show last exchange from current session."""
    session = session_mgr.get_current()
    
    if not session:
        console.print("[dim]No current session[/dim]")
        return
    
    if not session.messages:
        console.print(f"[dim]Session {session.id} is empty[/dim]")
        return
    
    # Show last 2 messages (user + assistant)
    console.print(f"[bold]Session {session.id}:[/bold]")
    console.print()
    
    messages_to_show = session.messages[-2:] if len(session.messages) >= 2 else session.messages
    
    for msg in messages_to_show:
        if msg.role == "user":
            console.print(f"[cyan]You:[/cyan] {msg.content}")
        elif msg.role == "assistant":
            console.print(f"[green]llmc:[/green] {msg.content}")
        console.print()


async def _show_status(config, session_mgr: SessionManager):
    """Show backend status."""
    
    agent = Agent(config)
    health = await agent.health_check()
    
    console.print(f"[bold]llmc-agent v{__version__}[/bold]")
    console.print()
    
    # Current session
    session = session_mgr.get_current()
    if session:
        msg_count = len(session.messages)
        console.print(f"[green]✓[/green] Session: {session.id} ({msg_count} messages)")
    else:
        console.print("[dim]○[/dim] Session: none active")
    
    # Ollama status
    ollama_ok = health.get("ollama", False)
    if ollama_ok:
        console.print(f"[green]✓[/green] Ollama: {config.ollama.url}")
        
        # List models
        models = await agent.ollama.list_models()
        if models:
            console.print(f"  Models: {', '.join(models[:5])}")
        console.print(f"  Default: {config.agent.model}")
    else:
        console.print(f"[red]✗[/red] Ollama: {config.ollama.url} (not responding)")
    
    # RAG status
    if config.rag.enabled:
        rag_ok = health.get("rag", False)
        if rag_ok:
            console.print("[green]✓[/green] RAG (LLMC): enabled")
            if agent.rag and agent.rag.repo_root:
                console.print(f"  Repo: {agent.rag.repo_root}")
        else:
            console.print("[yellow]○[/yellow] RAG (LLMC): fallback mode (ripgrep)")
    else:
        console.print("[dim]○[/dim] RAG: disabled")
    
    console.print()
    console.print("[dim]Session storage: ~/.llmc/sessions/[/dim]")
    console.print("[dim]Config paths: ~/.llmc/agent.toml, ./llmc.toml[/dim]")


if __name__ == "__main__":
    main()
