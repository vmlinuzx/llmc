from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import math
from statistics import mean

from .embeddings import build_embedding_backend


def build_backend():
    """Backwards compatible alias used by tests/legacy callers."""
    return build_embedding_backend()


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    paired = list(zip(a, b))
    if not paired:
        return 0.0
    dot = sum(x * y for x, y in paired)
    norm_a = math.sqrt(sum(x * x for x, _ in paired))
    norm_b = math.sqrt(sum(y * y for _, y in paired))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    query: str
    positives: Sequence[str]
    negatives: Sequence[str]


CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        name="jwt-verification",
        query="verify a json web token signature using an hmac secret",
        positives=(
            (
                "Validate a JWT by decoding the header and verifying the signature with an HMAC-SHA256 secret. "
                "Reject tokens whose exp claim is in the past before accepting the payload."
            ),
        ),
        negatives=(
            (
                "Generate a strong random password by sampling uppercase and lowercase characters together with digits and punctuation."
            ),
        ),
    ),
    BenchmarkCase(
        name="csv-parser",
        query="parse CSV text into a list of dictionaries keyed by headers",
        positives=(
            (
                "Split a CSV string into rows, zip the first line as headers, and emit dictionaries for each remaining line. "
                "Handle commas inside quoted cells correctly."
            ),
        ),
        negatives=(
            (
                "Render a hero banner component using Tailwind classes for gradient backgrounds and hover states."
            ),
        ),
    ),
    BenchmarkCase(
        name="http-retry",
        query="retry an http request with exponential backoff when it fails",
        positives=(
            (
                "Wrap a network fetch call in a loop that backs off exponentially between attempts. "
                "Stop retrying after the maximum retries or when a 200 status is returned."
            ),
        ),
        negatives=(
            (
                "Join the users and permissions tables in SQL to list all active administrators ordered by email."
            ),
        ),
    ),
    BenchmarkCase(
        name="fibonacci-memo",
        query="calculate fibonacci numbers using memoization or dynamic programming",
        positives=(
            (
                "Use a dictionary cache to memoize fibonacci(n). "
                "Seed with {0: 0, 1: 1} and reuse cached values before recursing to avoid exponential work."
            ),
        ),
        negatives=(
            (
                "Explain how to compute the median of an unsorted list by sorting and selecting the middle element."
            ),
        ),
    ),
)


def run_embedding_benchmark() -> dict[str, float]:
    backend = build_backend()
    hit_flags = []
    margins = []
    positive_scores = []
    negative_scores = []

    for case in CASES:
        query_vec = backend.embed_queries([case.query])[0]
        candidate_texts = list(case.positives) + list(case.negatives)
        candidate_labels = [1] * len(case.positives) + [0] * len(case.negatives)
        candidate_vecs = backend.embed_passages(candidate_texts)

        scores = [_dot(query_vec, vec) for vec in candidate_vecs]
        best_index = max(range(len(scores)), key=scores.__getitem__)
        hit_flags.append(1 if candidate_labels[best_index] == 1 else 0)

        best_positive = max(
            (s for s, label in zip(scores, candidate_labels) if label == 1), default=0.0
        )
        best_negative = max(
            (s for s, label in zip(scores, candidate_labels) if label == 0), default=0.0
        )
        margins.append(best_positive - best_negative)
        positive_scores.extend(s for s, label in zip(scores, candidate_labels) if label == 1)
        negative_scores.extend(s for s, label in zip(scores, candidate_labels) if label == 0)

    top1_accuracy = sum(hit_flags) / len(hit_flags) if hit_flags else 0.0
    avg_margin = mean(margins) if margins else 0.0
    avg_positive = mean(positive_scores) if positive_scores else 0.0
    avg_negative = mean(negative_scores) if negative_scores else 0.0

    return {
        "cases": float(len(CASES)),
        "top1_accuracy": float(top1_accuracy),
        "avg_margin": float(avg_margin),
        "avg_positive_score": float(avg_positive),
        "avg_negative_score": float(avg_negative),
    }
