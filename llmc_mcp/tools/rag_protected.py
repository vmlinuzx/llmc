#!/usr/bin/env python3
"""
MAASL-protected RAG enrichment operations.

Phase 4: DB Protection - wraps RAG database write operations with stomping protection.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
from typing import Any

from llmc_mcp.maasl import ResourceDescriptor, get_maasl

logger = logging.getLogger("llmc-mcp.rag.protected")


def enrich_spans_protected(
    db,  # Database instance (from llmc.rag.database)
    repo_root: Path,
    llm_call: Callable[[dict[str, Any]], dict[str, Any]],
    limit: int = 32,
    model: str = "local-llm",
    cooldown_seconds: int = 0,
    agent_id: str = "unknown",
    session_id: str = "unknown",
    operation_mode: str = "batch",
):
    """
    Enrich pending spans with MAASL DB protection.
    
    Wraps tools.rag.enrichment.enrich_spans with CRIT_DB lock protection.
    
    Args:
        db: Database instance
        repo_root: Repository root path
        llm_call: Callable for LLM enrichment
        limit: Max spans to process
        model: Model identifier
        cooldown_seconds: Skip recently modified files
        agent_id: ID of calling agent
        session_id: ID of calling session
        operation_mode: "interactive" or "batch" (default: batch for enrichment)
    
    Returns:
        EnrichmentBatchResult
    
    Raises:
        DbBusyError: If database is locked and retries exhausted
    """
    from llmc.rag.enrichment import enrich_spans
    
    # Create resource descriptor for MAASL lock
    resource = ResourceDescriptor(
        resource_class="CRIT_DB",
        identifier="rag",  # Logical database name
    )
    
    # Define protected operation
    def protected_enrich():
        """Execute enrichment within MAASL-protected section."""
        # The actual enrichment - already uses db.transaction() internally
        return enrich_spans(
            db=db,
            repo_root=repo_root,
            llm_call=llm_call,
            limit=limit,
            model=model,
            cooldown_seconds=cooldown_seconds,
            logger=logger,
        )
    
    # Execute with MAASL protection
    maasl = get_maasl()
    try:
        return maasl.call_with_stomp_guard(
            op=protected_enrich,
            resources=[resource],
            intent="rag_enrich",
            mode=operation_mode,
            agent_id=agent_id,
            session_id=session_id,
        )
    except Exception as e:
        # Log enrichment failures
        logger.error(f"Enrichment failed for {agent_id}: {e}")
        raise


def batch_enrich_protected(
    db,
    repo_root: Path,
    llm_call: Callable[[dict[str, Any]], dict[str, Any]],
    batch_size: int = 32,
    model: str = "local-llm",
    cooldown_seconds: int = 0,
    agent_id: str = "unknown",
    session_id: str = "unknown",
    operation_mode: str = "batch",
):
    """
    Batch enrich spans with MAASL DB protection.
    
    Wraps tools.rag.enrichment.batch_enrich with CRIT_DB lock protection.
    
    Args:
        db: Database instance
        repo_root: Repository root path
        llm_call: Callable for LLM enrichment
        batch_size: Spans to process in batch
        model: Model identifier
        cooldown_seconds: Skip recently modified files
        agent_id: ID of calling agent
        session_id: ID of calling session
        operation_mode: "interactive" or "batch"
    
    Returns:
        EnrichmentBatchResult
    
    Raises:
        DbBusyError: If database is locked and retries exhausted
    """
    # batch_enrich delegates to enrich_spans, so we just use the protected version
    return enrich_spans_protected(
        db=db,
        repo_root=repo_root,
        llm_call=llm_call,
        limit=batch_size,
        model=model,
        cooldown_seconds=cooldown_seconds,
        agent_id=agent_id,
        session_id=session_id,
        operation_mode=operation_mode,
    )


def store_enrichment_protected(
    db,
    span_hash: str,
    payload: dict,
    agent_id: str = "unknown",
    session_id: str = "unknown",
    operation_mode: str = "interactive",
):
    """
    Store single enrichment with MAASL DB protection.
    
    For one-off enrichment storage operations.
    
    Args:
        db: Database instance
        span_hash: Span hash to enrich
        payload: Enrichment data
        agent_id: ID of calling agent
        session_id: ID of calling session
        operation_mode: "interactive" or "batch"
    
    Raises:
        DbBusyError: If database is locked
    """
    resource = ResourceDescriptor(
        resource_class="CRIT_DB",
        identifier="rag",
    )
    
    def protected_store():
        """Execute store within transaction."""
        with db.transaction():
            db.store_enrichment(span_hash, payload)
        return True
    
    maasl = get_maasl()
    return maasl.call_with_stomp_guard(
        op=protected_store,
        resources=[resource],
        intent="store_enrichment",
        mode=operation_mode,
        agent_id=agent_id,
        session_id=session_id,
    )
