"""Integration test with real DeepSeek API."""

import os

import pytest

from llmc.rlm.config import RLMConfig
from llmc.rlm.session import RLMSession

try:
    LITELLM_INSTALLED = True
except ImportError:
    LITELLM_INSTALLED = False

# Sample code to analyze
SAMPLE_CODE = '''
def calculate_fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number recursively.
    
    This is intentionally inefficient for demonstration.
    """
    if n <= 1:
        return n
    return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)


class MathUtils:
    """Collection of math utilities."""
    
    @staticmethod
    def is_prime(n: int) -> bool:
        """Check if a number is prime."""
        if n < 2:
            return False
        for i in range(2, int(n ** 0.5) + 1):
            if n % i == 0:
                return False
        return True
    
    @staticmethod
    def factorial(n: int) -> int:
        """Calculate factorial."""
        if n <= 1:
            return 1
        return n * MathUtils.factorial(n - 1)
'''


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="DEEPSEEK_API_KEY not set"
)
@pytest.mark.skipif(
    not LITELLM_INSTALLED,
    reason="litellm not installed"
)
@pytest.mark.allow_network
async def test_rlm_deepseek_code_analysis():
    """Test RLM with real DeepSeek API analyzing Python code."""
    
    # Configure for DeepSeek
    config = RLMConfig(
        root_model="deepseek/deepseek-chat",
        sub_model="deepseek/deepseek-chat",
        max_session_budget_usd=0.10,  # 10 cents max
        trace_enabled=True,
    )
    
    # Set API key
    os.environ["DEEPSEEK_API_KEY"] = os.getenv("DEEPSEEK_API_KEY")
    
    # Create session
    session = RLMSession(config)
    
    # Load code
    meta = session.load_code_context(SAMPLE_CODE, language="python")
    
    print(f"\nContext loaded: {meta['total_chars']} chars, ~{meta['estimated_tokens']} tokens")
    print(f"Symbols indexed: {meta['symbol_count']}")
    
    # Run analysis
    task = "What are the performance issues in this code? List all functions with their complexity."
    
    print(f"\nTask: {task}")
    print("Running RLM session with DeepSeek...\n")
    
    result = await session.run(task, max_turns=10)
    
    # Verify results
    assert result is not None
    print(f"\nSuccess: {result.success}")
    print(f"Answer: {result.answer}")
    print("\nBudget Summary:")
    print(f"  Cost: ${result.budget_summary['total_cost_usd']:.4f}")
    print(f"  Root calls: {result.budget_summary['root_calls']}")
    print(f"  Sub calls: {result.budget_summary['sub_calls']}")
    print(f"  Total tokens: {result.budget_summary['total_tokens']:,}")
    print(f"  Time: {result.budget_summary['elapsed_seconds']:.1f}s")
    
    if result.trace:
        print(f"\nTrace events: {len(result.trace)}")
        for event in result.trace[:5]:  # Show first 5
            print(f"  - {event['event']}")
    
    if not result.success:
        print(f"\n⚠️ Session did not complete: {result.error}")
        
    # Assertions
    assert result.budget_summary['total_cost_usd'] <= config.max_session_budget_usd
    
    # Only assert tokens > 0 if success, otherwise we want to see the error above
    if result.success:
        assert result.budget_summary['total_tokens'] > 0
        assert result.answer is not None
        assert len(result.answer) > 0
        print("\n✅ RLM session completed successfully!")
    else:
        # Fail if not successful
        pytest.fail(f"RLM session failed: {result.error}")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="DEEPSEEK_API_KEY not set"
)
@pytest.mark.skipif(
    not LITELLM_INSTALLED,
    reason="litellm not installed"
)
async def test_rlm_deepseek_budget_enforcement():
    """Test that budget limits are enforced with DeepSeek."""
    
    config = RLMConfig(
        root_model="deepseek/deepseek-chat",
        sub_model="deepseek/deepseek-chat",
        max_session_budget_usd=0.01,  # Very low budget
        trace_enabled=False,
    )
    
    os.environ["DEEPSEEK_API_KEY"] = os.getenv("DEEPSEEK_API_KEY")
    
    session = RLMSession(config)
    session.load_code_context(SAMPLE_CODE, language="python")
    
    # This task should hit budget limit
    result = await session.run(
        "Perform a comprehensive analysis of this code including complexity, "
        "performance, best practices, refactoring suggestions, and security review.",
        max_turns=20
    )
    
    print(f"\nBudget test - Cost: ${result.budget_summary['total_cost_usd']:.4f}")
    print(f"Budget limit: ${config.max_session_budget_usd:.2f}")
    
    # Should not exceed budget
    assert result.budget_summary['total_cost_usd'] <= config.max_session_budget_usd * 1.1  # 10% grace
    
    print("✅ Budget enforcement works!")


if __name__ == "__main__":
    # For manual testing: DEEPSEEK_API_KEY=sk-xxx python tests/rlm/test_integration_deepseek.py
    import asyncio
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("Set DEEPSEEK_API_KEY environment variable")
        exit(1)
    
    print("Running DeepSeek integration test...\n")
    asyncio.run(test_rlm_deepseek_code_analysis())
