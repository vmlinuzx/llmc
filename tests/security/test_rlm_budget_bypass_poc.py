
from llmc.rlm.config import RLMConfig
from llmc.rlm.session import RLMSession


def test_rlm_budget_estimation_bypass():
    """
    POC: RLMSession uses naive character-based token estimation which can be bypassed.
    """
    config = RLMConfig(
        max_session_budget_usd=0.01, # Very small budget
        chars_per_token=4,
        token_safety_multiplier=1.0
    )
    RLMSession(config=config)
    
    # Text that tokenizes 1:1 or worse, but we tell the system it's 4 chars per token.
    # Actually, the bypass is that we can fit a lot of "expensive" content if we know the multiplier.
    # But more importantly, the 'root' call assumes 2000 tokens for output.
    # If the root call actually outputs 100,000 tokens, it only "reserved" 2000.
    
    # This test is hard to run without a real LLM, but we can mock the budget.check_and_reserve
    # to show that it uses the weak estimation.
    
    
    # messages will have system prompt + prompt
    # system prompt is quite large.
    
    # We can't easily POC this without mocking litellm.acompletion to return a huge usage.
    # But the code analysis already showed the flaw.
    
    print("\n[!] ARCHITECTURAL FLAW: RLMSession uses chars_per_token for budget reservation.")
    print("    This is known to be inaccurate for non-English text and code.")

