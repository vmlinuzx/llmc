#!/usr/bin/env python3
"""
Adversarial testing of the enrichment router system
"""

import sys

sys.path.insert(0, '/home/vmlinux/src/llmc')

from pathlib import Path


def test_enrichment_router_edge_cases():
    """Test edge cases in enrichment router."""

    print("=== ADVERSARIAL ENRICHMENT ROUTER TEST ===\n")

    # Test 1: Invalid EnrichmentSliceView construction
    print("Test 1: Invalid EnrichmentSliceView construction")
    try:
        from tools.rag.enrichment_router import EnrichmentSliceView

        # Test with None span_hash
        try:
            view = EnrichmentSliceView(
                span_hash=None,  # Invalid!
                file_path=Path("test.py"),
                start_line=1,
                end_line=10,
                content_type="code",
                classifier_confidence=0.8,
                approx_token_count=100,
            )
            print("  ⚠️  None span_hash accepted (should reject)")
        except Exception as e:
            print(f"  ✅ None span_hash rejected: {e}")

        # Test with negative confidence
        try:
            view = EnrichmentSliceView(
                span_hash="abc",
                file_path=Path("test.py"),
                start_line=1,
                end_line=10,
                content_type="code",
                classifier_confidence=-0.5,  # Invalid!
                approx_token_count=100,
            )
            print("  ⚠️  Negative confidence accepted (should reject)")
        except Exception as e:
            print(f"  ✅ Negative confidence rejected: {e}")

        # Test with inverted line numbers
        try:
            view = EnrichmentSliceView(
                span_hash="abc",
                file_path=Path("test.py"),
                start_line=50,
                end_line=10,  # start > end!
                content_type="code",
                classifier_confidence=0.8,
                approx_token_count=100,
            )
            print("  ⚠️  Inverted line numbers accepted (should reject)")
        except Exception as e:
            print(f"  ✅ Inverted line numbers rejected: {e}")

    except Exception as e:
        print(f"  💥 Import error: {e}")

    # Test 2: EnrichmentRouteDecision edge cases
    print("\nTest 2: EnrichmentRouteDecision edge cases")
    try:
        from tools.rag.config_enrichment import EnrichmentBackendSpec
        from tools.rag.enrichment_router import EnrichmentRouteDecision, EnrichmentSliceView

        # Test with None backend
        try:
            slice_view = EnrichmentSliceView(
                span_hash="abc",
                file_path=Path("test.py"),
                start_line=1,
                end_line=10,
                content_type="code",
                classifier_confidence=0.8,
                approx_token_count=100,
            )
            decision = EnrichmentRouteDecision(
                slice_view=slice_view,
                backend=None,  # Invalid!
                reason="test",
            )
            print("  ⚠️  None backend accepted (should reject)")
        except Exception as e:
            print(f"  ✅ None backend rejected: {e}")

        # Test with zero confidence
        try:
            backend = EnrichmentBackendSpec(
                name="test",
                chain="default",
                provider="test",
                enabled=True,
            )
            slice_view = EnrichmentSliceView(
                span_hash="abc",
                file_path=Path("test.py"),
                start_line=1,
                end_line=10,
                content_type="code",
                classifier_confidence=0.0,  # Very low!
                approx_token_count=100,
            )
            decision = EnrichmentRouteDecision(
                slice_view=slice_view,
                backend=backend,
                reason="zero confidence",
            )
            print(f"  ✅ Zero confidence accepted: {decision}")
        except Exception as e:
            print(f"  💥 Error with zero confidence: {e}")

    except Exception as e:
        print(f"  💥 Import/usage error: {e}")

    # Test 3: Database schema validation
    print("\nTest 3: Database schema validation")
    try:
        from tools.rag.enrichment_router import EnrichmentRouterMetricsEvent

        # Test with invalid metrics event
        try:
            # Invalid metric name (non-string)
            event = EnrichmentRouterMetricsEvent(
                timestamp=1234567890,
                query="test",
                route="code",
                confidence=0.8,
                metric_name=123,  # Invalid type!
                metric_value=1.0,
            )
            print("  ⚠️  Invalid metric_name type accepted")
        except Exception as e:
            print(f"  ✅ Invalid metric_name rejected: {e}")

        # Test with negative confidence
        try:
            event = EnrichmentRouterMetricsEvent(
                timestamp=1234567890,
                query="test",
                route="code",
                confidence=-0.5,  # Invalid!
                metric_name="test_metric",
                metric_value=1.0,
            )
            print("  ⚠️  Negative confidence accepted in metrics")
        except Exception as e:
            print(f"  ✅ Negative confidence rejected: {e}")

    except Exception as e:
        print(f"  💥 Error testing metrics: {e}")

    # Test 4: Very large token counts
    print("\nTest 4: Extreme values")
    try:
        view = EnrichmentSliceView(
            span_hash="x" * 1000,  # Very long hash
            file_path=Path("a" * 500 + ".py"),  # Very long path
            start_line=1,
            end_line=10**9,  # Billion lines!
            content_type="code",
            classifier_confidence=0.999999,  # Nearly 1
            approx_token_count=10**12,  # Trillion tokens!
        )
        print("  ⚠️  Extreme values accepted")
        print(f"     Token count: {view.approx_token_count:,}")
        print(f"     End line: {view.end_line:,}")
    except Exception as e:
        print(f"  ✅ Extreme values rejected: {e}")

    # Test 5: String path conversion
    print("\nTest 5: String path conversion")
    try:
        view1 = EnrichmentSliceView(
            span_hash="abc",
            file_path="test.py",  # String, not Path!
            start_line=1,
            end_line=10,
            content_type="code",
            classifier_confidence=0.8,
            approx_token_count=100,
        )
        if isinstance(view1.file_path, Path):
            print(f"  ✅ String converted to Path: {view1.file_path}")
        else:
            print(f"  ⚠️  String not converted to Path: {type(view1.file_path)}")
    except Exception as e:
        print(f"  💥 String conversion error: {e}")

    print("\n" + "="*60)
    print("ENRICHMENT ROUTER ADVERSARIAL TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    test_enrichment_router_edge_cases()
