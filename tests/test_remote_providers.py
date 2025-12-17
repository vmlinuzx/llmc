#!/usr/bin/env python3
"""
Unit tests for remote LLM provider infrastructure.

Tests:
- Reliability middleware (retry, rate limit, circuit breaker, cost tracking)
- Provider configuration loading
- Backend factory
"""

from pathlib import Path
import sys
import time

# Add repo to path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))


def test_backoff_calculation():
    """Test exponential backoff with jitter."""
    print("\n1. Testing exponential backoff calculation...")
    from llmc.rag.enrichment_reliability import calculate_backoff_delay

    # Test basic exponential growth
    delay0 = calculate_backoff_delay(0, base_seconds=1.0, jitter_pct=0.0)
    delay1 = calculate_backoff_delay(1, base_seconds=1.0, jitter_pct=0.0)
    delay2 = calculate_backoff_delay(2, base_seconds=1.0, jitter_pct=0.0)

    assert abs(delay0 - 1.0) < 0.01, f"Expected ~1s, got {delay0}"
    assert abs(delay1 - 2.0) < 0.01, f"Expected ~2s, got {delay1}"
    assert abs(delay2 - 4.0) < 0.01, f"Expected ~4s, got {delay2}"

    # Test max delay cap
    delay10 = calculate_backoff_delay(
        10, base_seconds=1.0, max_delay_seconds=60.0, jitter_pct=0.0
    )
    assert delay10 == 60.0, f"Expected 60s cap, got {delay10}"

    # Test with jitter
    delay_jitter = calculate_backoff_delay(1, base_seconds=1.0, jitter_pct=0.1)
    assert (
        2.0 <= delay_jitter <= 2.2
    ), f"Expected 2.0-2.2s with jitter, got {delay_jitter}"

    print("   ✓ Backoff calculation works correctly")


def test_rate_limiter():
    """Test token bucket rate limiter."""
    print("\n2. Testing rate limiter...")
    from llmc.rag.enrichment_reliability import RateLimitConfig, RateLimiter

    config = RateLimitConfig(
        requests_per_minute=10,
        tokens_per_minute=1000,
    )
    limiter = RateLimiter(config)

    # First request should proceed immediately
    delay = limiter.acquire(estimated_tokens=100)
    assert delay == 0.0, f"First request should have no delay, got {delay}"
    limiter.record(100)

    # More requests should still be fine
    for _ in range(8):
        delay = limiter.acquire(100)
        assert delay == 0.0, "Should still be under limit"
        limiter.record(100)

    # 10th request should be fine
    delay = limiter.acquire(100)
    assert delay == 0.0, "10th request should be fine"
    limiter.record(100)

    # 11th request should be rate limited (RPM exceeded)
    delay = limiter.acquire(100)
    assert delay > 0, f"11th request should be rate limited, got delay={delay}"

    print("   ✓ Rate limiter enforces RPM correctly")


def test_circuit_breaker():
    """Test circuit breaker state machine."""
    print("\n3. Testing circuit breaker...")
    from llmc.rag.enrichment_reliability import CircuitBreaker, CircuitBreakerConfig

    config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout_seconds=0.5,
    )
    breaker = CircuitBreaker(config)

    # Should start closed
    assert breaker.state == "closed"
    assert breaker.can_proceed() is True

    # Record failures
    breaker.record_failure()
    assert breaker.state == "closed"
    breaker.record_failure()
    assert breaker.state == "closed"
    breaker.record_failure()

    # Should open after threshold
    assert breaker.state == "open"
    assert breaker.can_proceed() is False

    # Wait for recovery timeout
    time.sleep(0.6)

    # Should transition to half-open
    assert breaker.can_proceed() is True
    assert breaker.state == "half_open"

    # Success should close it
    breaker.record_success()
    assert breaker.state == "closed"

    print("   ✓ Circuit breaker state transitions work correctly")


def test_cost_tracker():
    """Test cost tracking with budget caps."""
    print("\n4. Testing cost tracker...")
    from llmc.rag.enrichment_reliability import (
        CostTracker,
        CostTrackerConfig,
        PricingInfo,
    )

    pricing = {
        "test_provider": PricingInfo(
            input_per_million=0.10,
            output_per_million=0.30,
        )
    }

    config = CostTrackerConfig(
        pricing=pricing,
        daily_cap_usd=1.0,
        monthly_cap_usd=None,
    )

    tracker = CostTracker(config)

    # Should allow requests under budget
    assert tracker.check_budget("test_provider", 1_000_000) is True

    # Record some usage
    cost_info = tracker.record("test_provider", 1_000_000, 500_000)
    assert cost_info["cost_usd"] > 0

    # Should block when budget exceeded
    # 1M input = $0.10, 500K output = $0.15, total = $0.25
    # Need 3 more requests to exceed $1 cap
    tracker.record("test_provider", 1_000_000, 500_000)
    tracker.record("test_provider", 1_000_000, 500_000)
    tracker.record("test_provider", 1_000_000, 500_000)

    # Next request should be blocked
    assert tracker.check_budget("test_provider", 1_000_000) is False

    print("   ✓ Cost tracker enforces budget caps correctly")


def test_provider_registry():
    """Test provider configuration registry."""
    print("\n5. Testing provider registry...")
    from llmc.rag.enrichment_config import PROVIDERS, get_provider_metadata

    # Check known providers exist
    assert "ollama" in PROVIDERS
    assert "gemini" in PROVIDERS
    assert "openai" in PROVIDERS
    assert "anthropic" in PROVIDERS
    assert "groq" in PROVIDERS

    # Check metadata structure
    gemini = get_provider_metadata("gemini")
    assert gemini is not None
    assert gemini.adapter_type == "google-genai"
    assert gemini.auth_env_var == "GOOGLE_API_KEY"
    assert gemini.pricing is not None

    print("   ✓ Provider registry contains all expected providers")


def test_backend_factory():
    """Test backend factory can create adapters."""
    print("\n6. Testing backend factory...")
    from llmc.rag.config_enrichment import EnrichmentBackendSpec
    from llmc.rag.enrichment_factory import create_backend_from_spec

    # Test Ollama (should work without API key)
    spec = EnrichmentBackendSpec(
        name="test-ollama",
        provider="ollama",
        model="qwen2.5:7b",
        url="http://localhost:11434",
        timeout_seconds=30,
        enabled=True,
    )

    backend = create_backend_from_spec(spec)
    assert backend is not None
    assert hasattr(backend, "generate")
    assert hasattr(backend, "config")

    print("   ✓ Backend factory creates Ollama backend")

    # Note: We can't test remote providers without API keys in CI
    # but we can verify the factory logic works
    print("   ✓ Backend factory structure validated")


def test_adapter_exports():
    """Test that all adapters are properly exported."""
    print("\n7. Testing adapter exports...")
    from llmc.rag.enrichment_adapters import (
        AnthropicBackend,
        GeminiBackend,
        OllamaBackend,
        OpenAICompatBackend,
        RemoteBackend,
    )

    # Just verify they can be imported
    assert OllamaBackend is not None
    assert RemoteBackend is not None
    assert GeminiBackend is not None
    assert OpenAICompatBackend is not None
    assert AnthropicBackend is not None

    print("   ✓ All adapter classes are exported correctly")


def main():
    print("\n" + "=" * 60)
    print("REMOTE LLM PROVIDERS - Unit Tests")
    print("=" * 60)

    try:
        test_backoff_calculation()
        test_rate_limiter()
        test_circuit_breaker()
        test_cost_tracker()
        test_provider_registry()
        test_backend_factory()
        test_adapter_exports()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print()
        print("Remote LLM provider infrastructure is ready:")
        print("  ✓ Reliability middleware (retry, rate limit, circuit breaker)")
        print("  ✓ Cost tracking with budget caps")
        print("  ✓ Provider configuration registry")
        print("  ✓ Backend adapters (Gemini, OpenAI, Anthropic, Groq)")
        print("  ✓ Unified backend factory")
        print()
        print("Next: Add configuration to llmc.toml and test with real APIs")
        print()

        return 0

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
