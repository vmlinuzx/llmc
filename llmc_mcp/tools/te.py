"""
M5 Phase-1: TE wrapper tools

Provides a single MCP-exposed tool `te_run` that shells out to the TE CLI
with enforced `--json` output and injects LLMC session context env vars.

Design goals:
- Keep TE invisible to the model (MCP calls TE only).
- Stable JSON envelope: {"data": <parsed JSON or raw>, "meta": {...}}.
- Zero hard dependency on TE at import time; subprocess invoked at call.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import logging
import os
from pathlib import Path
import stat as stat_module
import subprocess
import time
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class PathSecurityError(Exception):
    """Raised when path access is denied for security reasons."""
    pass


# Optional imports: do not hard fail if absent (e.g., when running isolated tests).
try:
    from llmc_mcp.context import McpSessionContext  # added in your changes
except Exception:  # pragma: no cover - tolerate absence for unit tests
    McpSessionContext = None  # type: ignore

# Observability is optional here; wrapper degrades gracefully if not present.
try:
    from llmc_mcp.observability import ObservabilityContext, generate_correlation_id  # type: ignore
except Exception:  # pragma: no cover
    ObservabilityContext = None  # type: ignore

    def generate_correlation_id() -> str:
        return uuid.uuid4().hex[:8]


def _ensure_json_flag(args: Sequence[str]) -> Sequence[str]:
    """Guarantee that --json appears exactly once early in the argument list."""
    args = list(args)
    if "--json" not in args:
        # Insert early for better help/CLI behavior.
        args.insert(0, "--json")
    return args


def _validate_cwd(cwd: str | Path, allowed_roots: list[str]) -> Path:
    """
    Validate and normalize the CWD for safe execution.
    - Reuses the core path validation logic from `fs.py`.
    - Raises PathSecurityError on failure.
    """

    def normalize_path(path: str | Path) -> Path:
        """Normalize and resolve a path safely."""
        path_str = str(path)
        if "\x00" in path_str:
            raise PathSecurityError("Path contains null bytes")
        expanded = os.path.expanduser(path_str)
        return Path(expanded).resolve()

    def check_path_allowed(path: Path, roots: list[str]) -> bool:
        """Check if path is within allowed roots."""
        if not roots:
            return True
        resolved_roots = [Path(r).resolve() for r in roots]
        for root in resolved_roots:
            try:
                path.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    resolved = normalize_path(cwd)
    if not check_path_allowed(resolved, allowed_roots):
        raise PathSecurityError(f"CWD {resolved} is outside allowed roots: {allowed_roots}")

    return resolved


def _ctx_to_env(ctx) -> dict[str, str]:
    """
    Convert session context (if any) into namespaced env vars.
    Falls back to existing env when ctx is None.
    """
    env: dict[str, str] = {}

    # Prefer LLMC_TE_* but allow a downstream to still read legacy TE_*
    def put(k: str, v: str | None):
        if v is None:
            return
        env[f"LLMC_{k}"] = v
        # legacy compat
        env[k] = v

    if ctx and hasattr(ctx, "agent_id"):
        put("TE_AGENT_ID", str(ctx.agent_id))
    if ctx and hasattr(ctx, "session_id"):
        put("TE_SESSION_ID", str(ctx.session_id))
    if ctx and hasattr(ctx, "model"):
        put("TE_MODEL", str(ctx.model))
    return env


def _run_te(
    te_args: Sequence[str],
    *,
    ctx: McpSessionContext | None = None,
    timeout: float | None = None,
    cwd: str | None = None,
    extra_env: Mapping[str, str] | None = None,
    allowed_roots: list[str] | None = None,
) -> dict[str, Any]:
    """
    Execute TE with enforced --json and return a normalized envelope.
    {
      "data": <parsed_json or {"raw": "..."}>,
      "meta": {"returncode": int, "duration_s": float, "stderr": str, "argv": [...]}
    }
    """
    exe = "te"
    argv = [exe] + list(_ensure_json_flag(list(te_args)))
    env = dict(os.environ)
    env.update(_ctx_to_env(ctx))
    if extra_env:
        env.update({k: str(v) for k, v in extra_env.items()})

    started = time.time()
    try:
        validated_cwd = None
        if cwd:
            validated_cwd = _validate_cwd(cwd, allowed_roots or [])

        cp = subprocess.run(
            argv,
            capture_output=True,
            cwd=validated_cwd,
            timeout=timeout,
            env=env,
            text=True,
            check=False,
        )
        duration = time.time() - started
        stdout = (cp.stdout or "").strip()
        try:
            parsed = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            parsed = {"raw": stdout}

        return {
            "data": parsed,
            "meta": {
                "returncode": cp.returncode,
                "duration_s": duration,
                "stderr": cp.stderr,
                "argv": argv,
            },
        }
    except (Exception, PathSecurityError) as e:
        duration = time.time() - started
        # Structured failure path
        return {
            "data": {},
            "meta": {
                "returncode": -1,
                "duration_s": duration,
                "stderr": repr(e),
                "argv": argv,
                "error": True,
            },
        }


def te_run(
    args: Sequence[str],
    *,
    ctx: McpSessionContext | None = None,
    timeout: float | None = None,
    cwd: str | None = None,
    extra_env: Mapping[str, str] | None = None,
    allowed_roots: list[str] | None = None,
) -> dict[str, Any]:
    """
    Public tool entry point.
    Example:
        te_run(["run", "echo", "hello"])
    """
    corr = generate_correlation_id()
    if ObservabilityContext is not None:
        # If available, record timing + correlation in logs/metrics.
        with ObservabilityContext.scope(tool="te_run", correlation_id=corr):
            result = _run_te(
                args,
                ctx=ctx,
                timeout=timeout,
                cwd=cwd,
                extra_env=extra_env,
                allowed_roots=allowed_roots,
            )
            return result
    # Graceful degradation
    return _run_te(
        args, ctx=ctx, timeout=timeout, cwd=cwd, extra_env=extra_env, allowed_roots=allowed_roots
    )
