MAX_SUMMARY_WORDS = 60
MAX_LIST_ITEMS = 10

def truncate_words(text: str, max_words: int) -> tuple[str, bool]:
    """Truncate text with ellipsis, return (text, was_truncated)."""
    words = text.split()
    truncated = len(words) > max_words
    result = " ".join(words[:max_words]) + ("…" if truncated else "")
    return result, truncated

def truncate_list(items: list, max_items: int) -> tuple[list, bool]:
    """Truncate list to max items, return (list, was_truncated)."""
    truncated = len(items) > max_items
    return items[:max_items], truncated
