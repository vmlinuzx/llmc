"""Token budgeting that applies to BOTH root and sub-calls.

FIXES V1.1.0 ISSUE: Budget only enforced sub-calls.
Root calls could still drain budget unmonitored.

V1.1.1: All LLM calls go through the same budget enforcement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
import time
import tomllib
from typing import Literal

from llmc.core import find_repo_root, load_config

# Pricing loaded from config, not hardcoded
# FIXES V1.1.0 ISSUE: Hardcoded pricing will rot
DEFAULT_PRICING = {
    # Local (free)
    "ollama_chat/qwen3-8b": {"input": 0.0, "output": 0.0},
    "ollama_chat/qwen3-70b": {"input": 0.0, "output": 0.0},
    "ollama_chat/qwen3-next-80b": {"input": 0.0, "output": 0.0},
    # API (conservative defaults, override via config)
    "default": {"input": 0.01, "output": 0.03},
}


def load_pricing(config_path: Path | None = None) -> dict:
    """Load pricing from llmc.toml [rlm.pricing] section."""
    pricing = DEFAULT_PRICING.copy()
    
    data = {}
    if config_path:
        if config_path.is_file():
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
        elif config_path.is_dir():
            data = load_config(config_path)
    else:
        data = load_config(find_repo_root())
            
    if "rlm" in data and "pricing" in data["rlm"]:
        pricing.update(data["rlm"]["pricing"])
    
    return pricing


@dataclass
class BudgetConfig:
    """Budget configuration."""
    max_session_budget_usd: float = 1.00
    max_session_tokens: int = 500_000
    soft_limit_percentage: float = 0.80
    max_subcall_depth: int = 5  # Renamed from "recursion" - honest naming
    pricing: dict = field(default_factory=lambda: DEFAULT_PRICING)


@dataclass
class BudgetState:
    """Real-time budget tracking."""
    # Root call tracking
    root_input_tokens: int = 0
    root_output_tokens: int = 0
    root_cost_usd: float = 0.0
    root_calls: int = 0
    
    # Sub-call tracking  
    sub_input_tokens: int = 0
    sub_output_tokens: int = 0
    sub_cost_usd: float = 0.0
    sub_calls: int = 0
    current_subcall_depth: int = 0
    max_subcall_depth_reached: int = 0
    
    start_time: float = field(default_factory=time.time)
    
    @property
    def total_tokens(self) -> int:
        return (
            self.root_input_tokens + self.root_output_tokens +
            self.sub_input_tokens + self.sub_output_tokens
        )
    
    @property
    def total_cost_usd(self) -> float:
        return self.root_cost_usd + self.sub_cost_usd
    
    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time


class BudgetExceededError(Exception):
    """Raised when budget limits exceeded."""
    def __init__(
        self,
        message: str,
        accrued: float,
        projected: float,
        budget: float,
        call_type: Literal["root", "sub"],
        recoverable: bool = True,
    ):
        super().__init__(message)
        self.accrued = accrued
        self.projected = projected
        self.budget = budget
        self.call_type = call_type
        self.recoverable = recoverable


class DepthLimitError(Exception):
    """Raised when sub-call depth exceeded."""
    pass


class TokenBudget:
    """Unified budget manager for root AND sub-calls.
    
    V1.1.1 FIX: Budget enforcement applies to ALL calls.
    """
    
    def __init__(
        self,
        config: BudgetConfig,
        on_soft_limit: Callable[[str], None] | None = None,
    ):
        self.config = config
        self.state = BudgetState()
        self.on_soft_limit = on_soft_limit
        self._soft_warned = False
    
    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost using config pricing."""
        pricing = self.config.pricing.get(
            model, 
            self.config.pricing.get("default", {"input": 0.01, "output": 0.03})
        )
        return (
            (input_tokens / 1000) * pricing["input"] +
            (output_tokens / 1000) * pricing["output"]
        )
    
    def check_and_reserve(
        self,
        model: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        call_type: Literal["root", "sub"] = "sub",
    ) -> None:
        """Check budget before ANY call (root or sub).
        
        V1.1.1 FIX: Now called for root calls too, not just sub-calls.
        """
        projected_cost = self.estimate_cost(
            model, estimated_input_tokens, estimated_output_tokens
        )
        projected_total = self.state.total_cost_usd + projected_cost
        
        # Hard budget limit
        if projected_total > self.config.max_session_budget_usd:
            raise BudgetExceededError(
                f"Budget exceeded on {call_type} call: "
                f"${projected_total:.4f} > ${self.config.max_session_budget_usd:.2f}",
                accrued=self.state.total_cost_usd,
                projected=projected_cost,
                budget=self.config.max_session_budget_usd,
                call_type=call_type,
            )
        
        # Soft limit warning (once)
        soft_budget = self.config.max_session_budget_usd * self.config.soft_limit_percentage
        if not self._soft_warned and projected_total > soft_budget:
            self._soft_warned = True
            if self.on_soft_limit:
                self.on_soft_limit(
                    f"⚠️ Budget warning: Used ${self.state.total_cost_usd:.4f} "
                    f"of ${self.config.max_session_budget_usd:.2f} "
                    f"({self.config.soft_limit_percentage*100:.0f}% threshold). "
                    f"Please consolidate and call FINAL()."
                )
    
    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        call_type: Literal["root", "sub"] = "sub",
    ) -> float:
        """Record actual usage after call completes."""
        cost = self.estimate_cost(model, input_tokens, output_tokens)
        
        if call_type == "root":
            self.state.root_input_tokens += input_tokens
            self.state.root_output_tokens += output_tokens
            self.state.root_cost_usd += cost
            self.state.root_calls += 1
        else:
            self.state.sub_input_tokens += input_tokens
            self.state.sub_output_tokens += output_tokens
            self.state.sub_cost_usd += cost
            self.state.sub_calls += 1
        
        return cost
    
    def enter_subcall(self) -> int:
        """Enter sub-call level. Returns new depth."""
        self.state.current_subcall_depth += 1
        self.state.max_subcall_depth_reached = max(
            self.state.max_subcall_depth_reached,
            self.state.current_subcall_depth,
        )
        
        if self.state.current_subcall_depth > self.config.max_subcall_depth:
            raise DepthLimitError(
                f"Sub-call depth {self.state.current_subcall_depth} "
                f"exceeds limit {self.config.max_subcall_depth}"
            )
        
        return self.state.current_subcall_depth
    
    def exit_subcall(self) -> int:
        """Exit sub-call level."""
        self.state.current_subcall_depth = max(0, self.state.current_subcall_depth - 1)
        return self.state.current_subcall_depth
    
    def get_summary(self) -> dict:
        """Get budget summary."""
        return {
            "total_cost_usd": round(self.state.total_cost_usd, 4),
            "root_cost_usd": round(self.state.root_cost_usd, 4),
            "sub_cost_usd": round(self.state.sub_cost_usd, 4),
            "budget_usd": self.config.max_session_budget_usd,
            "budget_used_pct": round(
                (self.state.total_cost_usd / self.config.max_session_budget_usd) * 100, 1
            ),
            "total_tokens": self.state.total_tokens,
            "root_calls": self.state.root_calls,
            "sub_calls": self.state.sub_calls,
            "max_subcall_depth": self.state.max_subcall_depth_reached,
            "elapsed_seconds": round(self.state.elapsed_seconds, 1),
        }
