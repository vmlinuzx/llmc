"""RLM MCP Tool - Hospital-grade secure implementation per SDD v2."""

from __future__ import annotations

import asyncio
import fnmatch
import json
from pathlib import Path
from typing import Any

from llmc.rlm.config import load_rlm_config
from llmc.rlm.session import RLMSession, RLMResult
from llmc_mcp.config import McpRlmConfig
from llmc_mcp.tools.fs import validate_path


async def mcp_rlm_query(
    args: dict,
    config: McpRlmConfig,
    allowed_roots: list[str],
    repo_root: Path,
) -> dict:
    """Execute RLM query with security policy enforcement.
    
    Returns {data, meta} on success or {error, meta} on failure.
    Never includes `error` key in success responses.
    """
    
    # Feature flag check
    if not config.enabled:
        return {
            "error": "RLM tool is disabled",
            "meta": {"error_code": "tool_disabled", "retryable": False}
        }
    
    # Extract and validate args
    task = args.get("task", "").strip()
    path_arg = args.get("path")
    context_arg = args.get("context")
    budget_usd = args.get("budget_usd", 1.0)
    model_override = args.get("model")
    max_bytes = args.get("max_bytes", config.default_max_bytes)
    timeout_s = args.get("timeout_s", config.default_timeout_s)
    max_turns = args.get("max_turns", config.default_max_turns)
    language = args.get("language")
    
    # Validation: task length
    if not task or len(task) > 5000:
        return {
            "error": "Invalid task (must be 1-5000 chars)",
            "meta": {"error_code": "invalid_args", "retryable": False}
        }
    
    # Validation: oneOf (path xor context)
    if (path_arg and context_arg) or (not path_arg and not context_arg):
        return {
            "error": "Exactly one of 'path' or 'context' must be provided",
            "meta": {"error_code": "invalid_args", "retryable": False}
        }
    
    # Egress policy enforcement
    if model_override and not config.allow_model_override:
        return {
            "error": "Model override not allowed by policy",
            "meta": {
                "error_code": "egress_denied",
                "retryable": False,
                "remediation": "Set mcp.rlm.allow_model_override=true or remove 'model' argument"
            }
        }
    
    # Restricted profile: check model allowlist
    if config.profile == "restricted":
        rlm_config = load_rlm_config()
        model_to_check = model_override or rlm_config.root_model
        if not any(model_to_check.startswith(prefix) for prefix in config.allowed_model_prefixes):
            return {
                "error": f"Model '{model_to_check}' not in allowed prefixes for restricted profile",
                "meta": {
                    "error_code": "egress_denied",
                    "retryable": False,
                    "allowed_prefixes": config.allowed_model_prefixes
                }
            }
    
    # Initialize session
    rlm_config = load_rlm_config()
    if model_override:
        rlm_config.root_model = model_override
        rlm_config.sub_model = model_override
    
    # Override budget if requested
    if budget_usd:
        rlm_config.max_session_budget_usd = budget_usd
    
    # Disable trace for MCP (privacy)
    rlm_config.trace_enabled = False
    
    session = RLMSession(config=rlm_config)
    
    # Load context
    source_meta = {}
    try:
        if path_arg:
            # Path-based context with security enforcement
            if not config.allow_path:
                return {
                    "error": "Path-based queries disabled by policy",
                    "meta": {"error_code": "path_denied", "retryable": False}
                }
            
            resolved_path = validate_path(
                path_arg,
                allowed_roots=allowed_roots,
                repo_root=repo_root,
                operation="read_rlm_context"
            )
            
            # Denylist check
            for pattern in config.denylist_globs:
                if fnmatch.fnmatch(str(resolved_path), pattern):
                    return {
                        "error": f"File matches denylist pattern '{pattern}'",
                        "meta": {"error_code": "path_denied", "retryable": False}
                    }
            
            # Size check before read
            file_size = resolved_path.stat().st_size
            if file_size > max_bytes:
                return {
                    "error": f"File too large: {file_size:,} bytes (max {max_bytes:,})",
                    "meta": {
                        "error_code": "file_too_large",
                        "retryable": False,
                        "remediation": "Increase max_bytes or use 'context' with truncated text"
                    }
                }
            
            file_text = resolved_path.read_text(errors="replace")[:max_bytes]
            session.load_code_context(file_text, language=language)
            
            source_meta = {
                "type": "path",
                "path": str(resolved_path),
                "bytes_read": len(file_text.encode('utf-8')),
                "truncated": file_size > max_bytes
            }
        else:
            # Context-based
            session.load_context(context_arg)
            source_meta = {
                "type": "context",
                "bytes": len(context_arg.encode('utf-8'))
            }
    
    except FileNotFoundError:
        return {
            "error": f"File not found: {path_arg}",
            "meta": {"error_code": "file_not_found", "retryable": False}
        }
    except PermissionError as e:
        return {
            "error": f"Path denied: {e}",
            "meta": {"error_code": "path_denied", "retryable": False}
        }
    except ValueError as e:
        if "too large" in str(e):
            return {
                "error": str(e),
                "meta": {"error_code": "file_too_large", "retryable": False}
            }
        raise
    
    # Execute with timeout
    try:
        result: RLMResult = await asyncio.wait_for(
            session.run(task=task, max_turns=max_turns),
            timeout=timeout_s
        )
    except asyncio.TimeoutError:
        return {
            "error": f"Query exceeded timeout ({timeout_s}s)",
            "meta": {"error_code": "timeout", "retryable": True}
        }
    except Exception as e:
        import traceback
        return {
            "error": f"Internal error: {type(e).__name__}: {e}",
            "meta": {
                "error_code": "internal_error",
                "retryable": True,
                "traceback": traceback.format_exc()[:500]
            }
        }
    
    # Success response (MUST NOT include 'error' key)
    if result.success:
        return {
            "data": {
                "answer": result.answer,
                "session_id": result.session_id,
                "budget_summary": result.budget_summary or {}
            },
            "meta": {
                "source": source_meta,
                "model_used": rlm_config.root_model,
                "trace_included": False
            }
        }
    else:
        # RLM failed but didn't exception
        return {
            "error": result.error or "RLM session failed without answer",
            "meta": {
                "error_code": "rlm_failure",
                "retryable": False,
                "budget_summary": result.budget_summary
            }
        }
