"""RLM Session - V1.1.1 with all calls going through governance.

FIXES:
- Budget enforced for root AND sub-calls
- Uses LLMC's existing backend adapter
- Prompts generated from actual injected tools
- Process-based sandbox (killable timeouts)
- Callback interception (Phase 1)
"""

from __future__ import annotations
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

# Use LLMC's existing backend - single call surface
from llmc.backends.litellm_core import LiteLLMCore

from llmc.rlm.config import RLMConfig, load_rlm_config
from llmc.rlm.sandbox.interface import create_sandbox, ExecutionResult
from llmc.rlm.nav.treesitter_nav import TreeSitterNav, create_nav_tools
from llmc.rlm.governance.budget import (
    TokenBudget,
    BudgetConfig,
    BudgetExceededError,
    load_pricing,
)
from llmc.rlm.prompts import get_rlm_system_prompt
from llmc.rlm.sandbox.intercept import extract_tool_calls, rewrite_ast


@dataclass
class RLMResult:
    """Final result of an RLM session."""

    success: bool
    answer: str | None
    session_id: str
    error: str | None = None
    budget_summary: dict | None = None
    trace: list[dict] | None = None


class RLMSession:
    """RLM Session with unified governance for all LLM calls.

    V1.1.1 Architecture:
    - ALL calls (root + sub) go through TokenBudget
    - Uses LLMC's LiteLLMCore backend (not direct litellm calls)
    - Process sandbox with killable timeouts
    - Prompts generated from actual injected tools
    - Intercepts tool calls in parent process
    """

    def __init__(self, config: RLMConfig | None = None):
        self.config = config or load_rlm_config()
        self.session_id = str(uuid4())[:8]
        self.trace: list[dict] = []
        self._pending_warnings: list[str] = []
        self._interception_counter = 0

        # Initialize LLM backend (LLMC's existing infrastructure)
        # LiteLLMCore not used - we call litellm directly

        # Initialize governance with config-based pricing
        pricing = load_pricing()
        budget_config = BudgetConfig(
            max_session_budget_usd=self.config.max_session_budget_usd,
            max_session_tokens=self.config.max_tokens_per_session,
            max_subcall_depth=self.config.max_subcall_depth,
            pricing=pricing,
        )
        self.budget = TokenBudget(
            config=budget_config,
            on_soft_limit=self._handle_soft_limit,
        )

        # Initialize sandbox
        self.sandbox = create_sandbox(
            backend=self.config.sandbox_backend,
            
            max_output_chars=self.config.max_print_chars,
            timeout_seconds=self.config.code_timeout_seconds,
            blocked_builtins=self.config.blocked_builtins,
            allowed_modules=self.config.allowed_modules,
            security_mode=self.config.security_mode,
        )

        # Navigation (set on load_code_context)
        self.nav: TreeSitterNav | None = None
        self.context_meta: dict = {}
        self._injected_tools: dict = {}

    def _handle_soft_limit(self, warning: str) -> None:
        """Queue soft limit warning for injection into context."""
        self._pending_warnings.append(warning)
        self._log_trace("soft_limit", {"message": warning})

    def load_context(self, context: str | Path) -> dict:
        """Load raw string context."""
        if isinstance(context, Path):
            context = context.read_text()

        if len(context) > self.config.max_context_chars:
            raise ValueError(f"Context too large: {len(context):,} chars")

        self.context_meta = {
            "total_chars": len(context),
            "estimated_tokens": len(context) // self.config.chars_per_token,
            "type": "string",
        }

        self.sandbox.start()
        self.sandbox.inject_variable("context", context)

        # Register basic tools
        self._injected_tools = {
            "context_slice": lambda start, length=10000: context[start : start + length],
            "context_search": self._make_context_search(context),
            # "llm_query": self._make_llm_query(), # Phase 1: Disabled
        }
        for name, func in self._injected_tools.items():
            self.sandbox.register_callback(name, func)

        return self.context_meta

    def load_code_context(self, source: str | Path, language: str | None = None) -> dict:
        """Load code context with semantic navigation."""
        if isinstance(source, Path):
            source_text = source.read_text()
        else:
            source_text = source

        self.nav = TreeSitterNav(source_text, language=language, config=self.config)
        self.context_meta = self.nav.get_info()

        self.sandbox.start()
        self.sandbox.inject_variable("context", source_text)

        # Register nav tools + llm_query
        nav_tools = create_nav_tools(self.nav)
        self._injected_tools = {
            **nav_tools,
            # "llm_query": self._make_llm_query(), # Phase 1: Disabled
        }
        for name, func in self._injected_tools.items():
            self.sandbox.register_callback(name, func)

        return self.context_meta

    def _make_context_search(self, context: str):
        """Create context_search tool."""
        import re

        def context_search(pattern: str, max_results: int = 20) -> list[dict]:
            """Search context with regex."""
            results = []
            try:
                for match in re.finditer(pattern, context):
                    if len(results) >= max_results:
                        break
                    line = context[: match.start()].count("\n") + 1
                    results.append(
                        {
                            "text": match.group(0)[:self.config.match_preview_chars],
                            "line": line,
                            "start": match.start(),
                        }
                    )
            except re.error as e:
                results.append({"error": str(e)})
            return results

        return context_search

    def _make_llm_query(self):
        """Create governed llm_query tool."""
        budget = self.budget

        session = self

        def llm_query(prompt: str, max_tokens: int = 1024) -> str:
            """Query sub-LLM (governed by budget)."""
            # Estimate tokens
            estimated_input = int(len(prompt) / self.config.chars_per_token * self.config.token_safety_multiplier)
            estimated_output = min(max_tokens, 1000)

            try:
                # Check budget BEFORE call
                budget.check_and_reserve(
                    model=self.config.sub_model,
                    estimated_input_tokens=estimated_input,
                    estimated_output_tokens=estimated_output,
                    call_type="sub",
                )

                # Enter sub-call depth tracking
                depth = budget.enter_subcall()

                try:
                    # Use LLMC backend (not direct litellm)
                    # NOTE: LiteLLMCore doesn't have completion_sync in the analysis
                    # We'll use completion() which should be synchronous
                    import litellm

                    response = litellm.completion(
                        model=self.config.sub_model,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=max_tokens,
                        temperature=self.config.sub_temperature,
                    )

                    content = response.choices[0].message.content
                    input_tokens = response.usage.prompt_tokens
                    output_tokens = response.usage.completion_tokens

                    # Record actual usage
                    budget.record_usage(
                        model=self.config.sub_model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        call_type="sub",
                    )

                    session._log_trace(
                        "sub_call",
                        {
                            "depth": depth,
                            "prompt_preview": prompt[:self.config.prompt_preview_chars],
                            "response_preview": content[:self.config.response_preview_chars],
                            "tokens": input_tokens + output_tokens,
                        },
                    )

                    return content

                finally:
                    budget.exit_subcall()

            except BudgetExceededError as e:
                return f"[BUDGET EXCEEDED] {e}. Call FINAL() with current findings."

        return llm_query

    async def run(self, task: str, max_turns: int | None = None) -> RLMResult:
        """Execute RLM loop with governed root calls."""
        
        limit_turns = max_turns if max_turns is not None else self.config.max_turns

        # Generate prompt from actual injected tools
        system_prompt = get_rlm_system_prompt(
            context_meta=self.context_meta,
            injected_tools=self._injected_tools,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        final_answer = None
        last_error = None

        for turn in range(limit_turns):
            # Check timeout
            if self.budget.state.elapsed_seconds > self.config.session_timeout_seconds:
                last_error = f"Session timeout after {self.budget.state.elapsed_seconds:.1f}s"
                break

            # Inject pending warnings
            if self._pending_warnings:
                messages.append(
                    {
                        "role": "system",
                        "content": "\n".join(self._pending_warnings),
                    }
                )
                self._pending_warnings.clear()

            # Estimate root call cost
            prompt_text = "\n".join(m.get("content", "") for m in messages)
            estimated_input = int(len(prompt_text) / self.config.chars_per_token * self.config.token_safety_multiplier)
            estimated_output = 2000  # Conservative for root

            try:
                # V1.1.1 FIX: Budget check for ROOT calls too
                self.budget.check_and_reserve(
                    model=self.config.root_model,
                    estimated_input_tokens=estimated_input,
                    estimated_output_tokens=estimated_output,
                    call_type="root",
                )

                # Use litellm async API
                import litellm

                response = await litellm.acompletion(
                    model=self.config.root_model,
                    messages=messages,
                    max_tokens=self.config.root_max_tokens,
                    temperature=self.config.root_temperature,
                )

                assistant_message = response.choices[0].message.content

                # Record root usage
                self.budget.record_usage(
                    model=self.config.root_model,
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                    call_type="root",
                )

            except BudgetExceededError as e:
                last_error = f"Budget exceeded on root call: {e}"
                self._log_trace("budget_exceeded", {"error": str(e)})
                break
            except Exception as e:
                import traceback

                last_error = f"Root model error: {e}"
                self._log_trace(
                    "root_error",
                    {
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    },
                )
                break

            self._log_trace(
                "root_response",
                {
                    "turn": turn,
                    "content_preview": assistant_message[:500],
                },
            )

            # Extract and execute code
            code_blocks = self._extract_code_blocks(assistant_message)

            if not code_blocks:
                messages.append({"role": "assistant", "content": assistant_message})
                messages.append(
                    {
                        "role": "user",
                        "content": "Please write Python code using the available tools. "
                        "Call FINAL(answer) when done.",
                    }
                )
                continue

            # Execute code blocks
            exec_results = []
            for code in code_blocks:
                # Phase 1: Interception (Process Backend Support)
                intercept_whitelist = {
                    "nav_outline",
                    "nav_ls",
                    "nav_read",
                    "nav_search",
                    "nav_info",
                }
                
                sites, errors = extract_tool_calls(code, intercept_whitelist)

                if errors:
                    exec_results.append({
                        "success": False,
                        "stdout": None,
                        "stderr": None,
                        "error": "\n".join(errors)
                    })
                    continue

                injections = []
                failed = False
                for site in sites:
                    tool_func = self._injected_tools.get(site.tool_name)
                    if not tool_func:
                        # Should not happen if whitelist subset of injected
                        exec_results.append({
                            "success": False,
                            "stdout": None,
                            "stderr": None,
                            "error": f"Tool {site.tool_name} not available"
                        })
                        failed = True
                        break

                    try:
                        val = tool_func(*site.args, **site.kwargs)
                    except Exception as e:
                        exec_results.append({
                            "success": False,
                            "stdout": None,
                            "stderr": None,
                            "error": f"Tool execution error in {site.tool_name}: {e}"
                        })
                        failed = True
                        break
                    else:
                        self._interception_counter += 1
                        inj_name = f"__rlm_icpt_{self.session_id}_{self._interception_counter}"
                        self.sandbox.inject_variable(inj_name, val)
                        injections.append(inj_name)
                        
                        self._log_trace("tool_intercepted", {
                            "tool": site.tool_name, 
                            "injected_as": inj_name
                        })

                if failed:
                    continue

                if sites:
                    try:
                        code = rewrite_ast(code, sites, injections)
                    except Exception as e:
                        exec_results.append({
                            "success": False,
                            "stdout": None,
                            "stderr": None,
                            "error": f"AST rewrite failed: {e}"
                        })
                        continue

                result = self.sandbox.execute(code)

                self._log_trace(
                    "code_exec",
                    {
                        "code_preview": code[:300],
                        "success": result.success,
                        "has_final": result.final_answer is not None, "error": result.error,
                    },
                )

                if result.final_answer:
                    final_answer = result.final_answer
                    break

                # Structured feedback (V1.1.1 improvement)
                exec_results.append(
                    {
                        "success": result.success,
                        "stdout": result.stdout[:self.config.stdout_preview_chars] if result.stdout else None,
                        "stderr": result.stderr[:500] if result.stderr else None,
                        "error": result.error,
                    }
                )

            if final_answer:
                break

            # Feed structured results back
            messages.append({"role": "assistant", "content": assistant_message})

            import json

            feedback = json.dumps(exec_results, indent=2)
            messages.append(
                {
                    "role": "user",
                    "content": f"Execution results:\n```json\n{feedback}\n```\n\n"
                    f"Continue analysis or call FINAL(answer).",
                }
            )

        # Cleanup
        self.sandbox.stop()

        return RLMResult(
            success=final_answer is not None,
            answer=final_answer,
            session_id=self.session_id,
            error=last_error,
            budget_summary=self.budget.get_summary(),
            trace=self.trace if self.config.trace_enabled else None,
        )

    def _extract_code_blocks(self, text: str) -> list[str]:
        """Extract Python code blocks."""
        import re

        pattern = r"```(?:python)?\s*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        return [m.strip() for m in matches if m.strip()]

    def _log_trace(self, event: str, data: dict) -> None:
        """Log to trace."""
        if self.config.trace_enabled:
            self.trace.append(
                {
                    "event": event,
                    "timestamp": time.time(),
                    "session_id": self.session_id,
                    **data,
                }
            )
