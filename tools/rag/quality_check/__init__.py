#!/usr/bin/env python3
"""
Language-aware canonical classifier for enrichment quality assessment.

Rule Version: v1-cjk-aware (2025-11-12)

Classifies summaries into exactly one terminal class:
- OK: Contentful and acceptable
- SHORT: Too terse for language/length rules
- PLACEHOLDER: Known fake/boilerplate patterns
- EMPTY: Only whitespace/punctuation after normalization
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional

# Rule version for telemetry and regression tracking
RULE_VERSION = "v1-cjk-aware"

# CJK Unicode ranges
CJK_RANGE = r'[\u4e00-\u9fff]'  # Han (Chinese)
KANA_RANGE = r'[\u3040-\u30ff]'  # Hiragana + Katakana (Japanese)
HANGUL_RANGE = r'[\uac00-\ud7af]'  # Hangul (Korean)
CJK_PATTERN = re.compile(f'({CJK_RANGE}|{KANA_RANGE}|{HANGUL_RANGE})')

# Placeholder patterns (case-insensitive)
PLACEHOLDER_PATTERNS = [
    r'auto-summary generated offline',
    r'\bplaceholder\b',
    r'\blorem\b',
    r'\btodo\b',
    r'\btbd\b',
    r'\bfake\b',
    r'^\s*-\s*$',  # Just a dash
    r'^\s*—\s*$',  # Just an em dash
    r'^\s*\.\.\.\s*$',  # Just ellipsis
    r'^\s*\*\*\*\s*$',  # Just asterisks
]

# Punctuation to strip during normalization (ASCII + common Unicode)
PUNCTUATION_TO_STRIP = r'[\s\t\n\r.,;:!?()\[\]{}"\'`~…—–•。、《》，；：' + "'" + r']+'

QualityClass = Literal['OK', 'SHORT', 'PLACEHOLDER', 'EMPTY']


@dataclass
class QualityResult:
    """Result of quality classification."""
    classification: QualityClass
    reason: str
    rule_version: str = RULE_VERSION


def normalize_text(text: str) -> str:
    """
    Normalize text by stripping whitespace and common punctuation.

    Args:
        text: Input summary text

    Returns:
        Normalized text (stripped of punctuation and whitespace)
    """
    # Strip whitespace
    normalized = text.strip()

    # Strip common punctuation (ASCII + Unicode variants)
    normalized = re.sub(PUNCTUATION_TO_STRIP, ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


def has_cjk(text: str) -> bool:
    """
    Detect if text contains CJK characters.

    Args:
        text: Input text

    Returns:
        True if CJK characters present, False otherwise
    """
    return bool(CJK_PATTERN.search(text))


def count_english_tokens(text: str) -> int:
    """
    Count alphanumeric tokens in English text.

    Args:
        text: Input text

    Returns:
        Number of alphanumeric tokens (words)
    """
    # Remove CJK characters and split on whitespace
    no_cjk = CJK_PATTERN.sub('', text)
    tokens = re.findall(r'\w+', no_cjk)
    return len(tokens)


def check_placeholder(text: str) -> Optional[QualityResult]:
    """
    Check if text matches known placeholder patterns.

    Args:
        text: Input summary text

    Returns:
        QualityResult with PLACEHOLDER classification if matched, None otherwise
    """
    text_lower = text.lower().strip()

    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, text_lower):
            return QualityResult(
                classification='PLACEHOLDER',
                reason=f'pattern={pattern}',
                rule_version=RULE_VERSION
            )

    return None


def classify_quality(summary: str, normalized_text: Optional[str] = None) -> QualityResult:
    """
    Canonical classifier for enrichment quality.

    Implements language-aware rules (v1-cjk-aware):
    - PLACEHOLDER: Match against known patterns (—, ..., ***, auto-summary, etc.)
    - EMPTY: Only whitespace/punctuation after normalization
    - CJK text: OK if ≥10 chars (Chinese, Japanese, Korean)
    - English text: OK if ≥2 tokens, SHORT if <5 tokens AND <10 chars

    Classification priority (first match wins):
    1. Check for placeholders (before normalization)
    2. Check if empty after normalization
    3. Check CJK length threshold
    4. Check English token count

    Args:
        summary: Original summary text
        normalized_text: Optional pre-normalized text (for efficiency)

    Returns:
        QualityResult with classification, reason, and rule_version
    """
    if not summary or not summary.strip():
        return QualityResult(
            classification='EMPTY',
            reason='no-content',
            rule_version=RULE_VERSION
        )

    # Check for placeholders FIRST (before normalization)
    # This catches cases like "—" and "..." that normalize to empty
    placeholder_result = check_placeholder(summary)
    if placeholder_result:
        return placeholder_result

    # Normalize text
    if normalized_text is None:
        normalized_text = normalize_text(summary)

    # Check if empty after normalization
    if not normalized_text:
        return QualityResult(
            classification='EMPTY',
            reason='punctuation-only',
            rule_version=RULE_VERSION
        )

    # Detect CJK presence
    has_cjk_chars = has_cjk(normalized_text)

    if has_cjk_chars:
        # CJK text: OK if length ≥ 10 chars
        cjk_length = len(normalized_text)
        if cjk_length >= 10:
            return QualityResult(
                classification='OK',
                reason=f'cjk={cjk_length} chars',
                rule_version=RULE_VERSION
            )
        else:
            return QualityResult(
                classification='SHORT',
                reason=f'cjk-too-short={cjk_length} chars',
                rule_version=RULE_VERSION
            )
    else:
        # English/space-separated text: Count tokens
        token_count = count_english_tokens(normalized_text)
        total_length = len(normalized_text)

        # OK if ≥2 tokens (allows "Initialize configuration")
        if token_count >= 2:
            return QualityResult(
                classification='OK',
                reason=f'en={token_count} tokens',
                rule_version=RULE_VERSION
            )
        # SHORT if <5 tokens AND very short total length
        elif token_count < 5 and total_length < 10:
            return QualityResult(
                classification='SHORT',
                reason=f'en-too-short={token_count} tokens, {total_length} chars',
                rule_version=RULE_VERSION
            )
        # Otherwise OK (handles edge cases)
        else:
            return QualityResult(
                classification='OK',
                reason=f'en-edge-case={token_count} tokens',
                rule_version=RULE_VERSION
            )


def test_classifier():
    """Test classifier against the gold set."""
    import csv
    from pathlib import Path

    goldset_path = Path(__file__).resolve().parents[2] / 'qa' / 'goldset_en_cjk.csv'

    if not goldset_path.exists():
        print(f"WARNING: Gold set not found at {goldset_path}")
        return

    with open(goldset_path) as f:
        reader = csv.DictReader(f)
        print(f"\n{'Testing classifier against gold set':=^70}")
        print(f"Rule version: {RULE_VERSION}\n")

        passed = 0
        failed = 0

        for row in reader:
            row_id = row['row_id']
            summary = row['summary']
            expected = row['expected_class']

            result = classify_quality(summary)
            actual = result.classification

            if actual == expected:
                print(f"✓ {row_id}: {actual} (OK)")
                passed += 1
            else:
                print(f"✗ {row_id}: expected {expected}, got {actual}")
                print(f"  Summary: {summary[:60]}")
                print(f"  Reason: {result.reason}")
                failed += 1

        total = passed + failed
        print(f"\n{'='*70}")
        print(f"Results: {passed}/{total} passed ({passed/total*100:.1f}%)")
        print(f"{'='*70}\n")

        return failed == 0


if __name__ == '__main__':
    # Run tests when called directly
    success = test_classifier()
    exit(0 if success else 1)
