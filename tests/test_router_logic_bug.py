"""Test for router promotion logic bug."""

from scripts.router import RouterSettings, choose_next_tier_on_failure


def test_router_promote_once_false_should_return_none():
    """Test that promote_once=False returns None (no more promotion).

    This is testing a BUG in the current implementation where the logic
    is inverted. When promote_once=False, we should NOT promote further.
    """
    settings = RouterSettings()

    # Test with 7b tier and a failure that would normally promote
    next_tier = choose_next_tier_on_failure(
        failure_type="parse",
        current_tier="7b",
        metrics={},
        settings=settings,
        promote_once=False,
    )

    # When promote_once=False, we should NOT promote at all.
    # This test verifies the fix for a previous bug where it returned "nano".
    print(f"Next tier with promote_once=False: {next_tier}")
    assert next_tier is None, f"Expected None but got {next_tier}"


def test_router_promote_once_true_should_promote():
    """Test that promote_once=True allows promotion."""
    settings = RouterSettings()

    # Test with 7b tier and a failure that would promote
    next_tier = choose_next_tier_on_failure(
        failure_type="parse",
        current_tier="7b",
        metrics={},
        settings=settings,
        promote_once=True,
    )

    # Should promote to 14b
    assert next_tier == "14b"


def test_router_promote_once_with_truncation():
    """Test promotion logic with truncation failure."""
    settings = RouterSettings()

    # Truncation always goes to nano
    next_tier = choose_next_tier_on_failure(
        failure_type="truncation",
        current_tier="7b",
        metrics={},
        settings=settings,
        promote_once=True,
    )

    assert next_tier == "nano"


def test_router_promote_once_with_14b():
    """Test promotion logic with 14b tier."""
    settings = RouterSettings()

    # 14b should always go to nano (downgrade)
    next_tier = choose_next_tier_on_failure(
        failure_type="parse",
        current_tier="14b",
        metrics={},
        settings=settings,
        promote_once=True,
    )

    assert next_tier == "nano"


def test_router_promote_once_with_nano():
    """Test promotion logic with nano tier."""
    settings = RouterSettings()

    # Nano can't be promoted further
    next_tier = choose_next_tier_on_failure(
        failure_type="parse",
        current_tier="nano",
        metrics={},
        settings=settings,
        promote_once=True,
    )

    assert next_tier is None


def test_router_fallback_logic():
    """Test the fallback logic at end of function."""
    settings = RouterSettings()

    # For unknown failure types with promote_once=True
    next_tier = choose_next_tier_on_failure(
        failure_type="completely_unknown_failure",
        current_tier="7b",
        metrics={},
        settings=settings,
        promote_once=True,
    )

    # Should return nano (the fallback)
    assert next_tier == "nano"

    # But with promote_once=False, should return None
    next_tier = choose_next_tier_on_failure(
        failure_type="completely_unknown_failure",
        current_tier="7b",
        metrics={},
        settings=settings,
        promote_once=False,
    )

    # This checks that even for unknown failures, promote_once=False returns None.
    print(f"Unknown failure with promote_once=False: {next_tier}")
    assert next_tier is None
