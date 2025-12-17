import pytest
from llmc.rag.enrichment.budgets import truncate_words, truncate_list, MAX_SUMMARY_WORDS, MAX_LIST_ITEMS

def test_truncate_words_under_limit():
    text = "This is a short text."
    result, truncated = truncate_words(text, 10)
    assert result == text
    assert not truncated

def test_truncate_words_over_limit():
    text = "This is a test text for truncation."
    result, truncated = truncate_words(text, 5)
    assert result == "This is a test text…"
    assert truncated

def test_truncate_words_returns_flag():
    text = "Word " * 10
    result, truncated = truncate_words(text, 5)
    assert truncated is True
    result, truncated = truncate_words(text, 20)
    assert truncated is False

def test_truncate_list_under_limit():
    items = [1, 2, 3]
    result, truncated = truncate_list(items, 5)
    assert result == items
    assert not truncated

def test_truncate_list_over_limit():
    items = [1, 2, 3, 4, 5, 6]
    result, truncated = truncate_list(items, 3)
    assert result == [1, 2, 3]
    assert truncated
