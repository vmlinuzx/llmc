"""Test token budget system."""

import pytest
from llmc.rlm.governance.budget import (
    TokenBudget,
    BudgetConfig,
    BudgetExceededError,
)


class TestTokenBudget:
    def test_budget_enforced_for_root_calls(self):
        """V1.1.1 FIX: Budget applies to root, not just sub."""
        config = BudgetConfig(max_session_budget_usd=0.001)  # Very low
        budget = TokenBudget(config)
        
        # Root call should be checked
        with pytest.raises(BudgetExceededError) as exc_info:
            budget.check_and_reserve(
                model="gpt-4o",
                estimated_input_tokens=10000,
                estimated_output_tokens=5000,
                call_type="root",  # V1.1.1: Now supports root
            )
        
        assert exc_info.value.call_type == "root"
    
    def test_soft_limit_callback_fires_once(self):
        """Soft limit warning fires exactly once."""
        warnings = []
        config = BudgetConfig(
            max_session_budget_usd=1.00,
            soft_limit_percentage=0.10,  # 10% = $0.10
        )
        budget = TokenBudget(config, on_soft_limit=warnings.append)
        
        # First call pushes past 10%
        budget.record_usage("mock", 5000, 5000, "sub")  # ~$0.20 at default pricing
        budget.check_and_reserve("mock", 100, 100, "sub")
        
        assert len(warnings) == 1
        
        # Second call should NOT re-warn
        budget.check_and_reserve("mock", 100, 100, "sub")
        assert len(warnings) == 1  # Still 1
    
    def test_pricing_from_config(self):
        """Pricing loaded from config, not hardcoded."""
        custom_pricing = {
            "my-model": {"input": 0.001, "output": 0.002},
            "default": {"input": 0.01, "output": 0.03},
        }
        config = BudgetConfig(pricing=custom_pricing)
        budget = TokenBudget(config)
        
        cost = budget.estimate_cost("my-model", 1000, 1000)
        expected = (1000/1000 * 0.001) + (1000/1000 * 0.002)  # $0.003
        
        assert abs(cost - expected) < 0.0001
    
    def test_subcall_depth_tracking(self):
        """Sub-call depth is tracked correctly."""
        config = BudgetConfig(max_subcall_depth=3)
        budget = TokenBudget(config)
        
        assert budget.enter_subcall() == 1
        assert budget.enter_subcall() == 2
        assert budget.enter_subcall() == 3
        
        budget.exit_subcall()
        assert budget.state.current_subcall_depth == 2
    
    def test_local_model_pricing(self):
        """Local models have zero cost."""
        config = BudgetConfig()
        budget = TokenBudget(config)
        
        cost = budget.estimate_cost("ollama_chat/qwen3-next-80b", 10000, 5000)
        assert cost == 0.0
