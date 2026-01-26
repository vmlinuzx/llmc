import pytest

from llmc.rag.extractors.context_detector import (
    ContextDetector,
    detect_context,
    detect_negation,
)


def test_detect_negation():
    """Test negation detection for 'Patient denies chest pain'"""
    text = "Patient denies chest pain"
    entity = "chest pain"

    # Find the position of the entity in the text
    start = text.find(entity)
    assert start != -1, f"Entity '{entity}' not found in text"
    end = start + len(entity)
    entity_span = (start, end)

    # Test using the class method
    detector = ContextDetector()
    result = detector.detect_negation(text, entity_span)
    assert result, f"Expected 'chest pain' to be negated in '{text}'"

    # Test using the convenience function
    result_func = detect_negation(text, entity_span)
    assert result_func, "Convenience function should also detect negation"


def test_detect_context_negation():
    """Test context detection for 'Patient denies chest pain' - should be negated"""
    text = "Patient denies chest pain"
    entity = "chest pain"

    start = text.find(entity)
    end = start + len(entity)
    entity_span = (start, end)

    detector = ContextDetector()
    result = detector.detect_context(text, entity_span)

    assert result["negated"], "Expected 'chest pain' to be negated"
    assert not result["historical"], "Should not be historical"
    assert not result["family"], "Should not be family"
    assert not result["hypothetical"], "Should not be hypothetical"

    # Test convenience function
    result_func = detect_context(text, entity_span)
    assert result_func == result


def test_detect_context_historical():
    """Test context detection for 'history of diabetes' - should be historical"""
    text = "history of diabetes"
    entity = "diabetes"

    start = text.find(entity)
    end = start + len(entity)
    entity_span = (start, end)

    detector = ContextDetector()
    result = detector.detect_context(text, entity_span)

    assert result["historical"], "Expected 'diabetes' to be historical"
    assert not result["negated"], "Should not be negated"
    assert not result["family"], "Should not be family"
    assert not result["hypothetical"], "Should not be hypothetical"


def test_detect_context_family():
    """Test context detection for 'mother had cancer' - should be family"""
    text = "mother had cancer"
    entity = "cancer"

    start = text.find(entity)
    end = start + len(entity)
    entity_span = (start, end)

    detector = ContextDetector()
    result = detector.detect_context(text, entity_span)

    assert result["family"], "Expected 'cancer' to be family history"
    assert not result["negated"], "Should not be negated"
    assert (
        not result["historical"]
    ), "Should not be historical (it's family, not patient's history)"
    assert not result["hypothetical"], "Should not be hypothetical"


def test_detect_context_multiple_categories():
    """Test when entity matches multiple context categories"""
    text = "No family history of diabetes"
    entity = "diabetes"

    start = text.find(entity)
    end = start + len(entity)
    entity_span = (start, end)

    detector = ContextDetector()
    result = detector.detect_context(text, entity_span)

    # 'No' indicates negation, 'family history' indicates family
    assert result["negated"], "Expected 'diabetes' to be negated due to 'No'"
    assert (
        result["family"]
    ), "Expected 'diabetes' to be family due to 'family history'"
    assert (
        not result["historical"]
    ), "Should not be historical (it's family history)"
    assert not result["hypothetical"], "Should not be hypothetical"


def test_detect_context_hypothetical():
    """Test hypothetical context detection"""
    text = "If patient has fever, consider infection"
    entity = "infection"

    start = text.find(entity)
    end = start + len(entity)
    entity_span = (start, end)

    detector = ContextDetector()
    result = detector.detect_context(text, entity_span)

    assert (
        result["hypothetical"]
    ), "Expected 'infection' to be hypothetical due to 'consider'"
    assert not result["negated"], "Should not be negated"
    assert not result["historical"], "Should not be historical"
    assert not result["family"], "Should not be family"


def test_detect_context_no_context():
    """Test when entity has no special context"""
    text = "Patient has headache"
    entity = "headache"

    start = text.find(entity)
    end = start + len(entity)
    entity_span = (start, end)

    detector = ContextDetector()
    result = detector.detect_context(text, entity_span)

    assert not result["negated"], "Should not be negated"
    assert not result["historical"], "Should not be historical"
    assert not result["family"], "Should not be family"
    assert not result["hypothetical"], "Should not be hypothetical"


def test_context_window():
    """Test that context window is correctly calculated"""
    detector = ContextDetector()

    # Create a text where the entity is in the middle
    text = "a" * 100 + "Patient denies chest pain" + "b" * 100
    entity = "chest pain"

    start = text.find(entity)
    end = start + len(entity)
    entity_span = (start, end)

    # The window should capture "denies" which is before the entity
    result = detector.detect_negation(text, entity_span)
    assert result, "Should detect negation even with surrounding text"


def test_entity_not_found():
    """Test behavior when entity is not in text"""
    text = "Patient denies chest pain"
    entity = "headache"

    start = text.find(entity)
    # start will be -1 when entity is not found
    if start == -1:
        # This is expected, we should handle this case
        # In real usage, we should ensure entity is in text
        pass
    else:
        end = start + len(entity)
        entity_span = (start, end)
        # This shouldn't happen in our tests since we're careful
        detector = ContextDetector()
        detector.detect_context(text, entity_span)
        # The result may be unexpected since entity isn't actually in the text


def test_case_insensitivity():
    """Test that patterns are case-insensitive"""
    text = "Patient DENIES chest pain"
    entity = "chest pain"

    start = text.find(entity)
    end = start + len(entity)
    entity_span = (start, end)

    detector = ContextDetector()
    result = detector.detect_negation(text, entity_span)

    assert result, "Should detect negation even with uppercase 'DENIES'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
